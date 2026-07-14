"""gemini_client.py — optional cloud LLM provider. Use this when you want
stronger reasoning than a local 7-8B model can reliably give (e.g. for
step 3's source-relevance explanations), at the cost of that content
leaving the machine. Get a free API key at https://aistudio.google.com/apikey

API Key Rotation & round-robin request usage
---------------------------------------------
Set GEMINI_API_KEY to a comma-separated list of keys to enable automatic
round-robin rotation across requests.

    GEMINI_API_KEY=key1,key2,key3

Behaviour on 429 / quota-exceeded:
    1. The client does not retry the same request with a different key.
    2. Each request uses exactly one Gemini key.
    3. Keys rotate to the next one only on the next logical request.

For non-quota errors (network failures, invalid prompts, etc.) the client
falls back to Ollama immediately without cycling through keys.
"""

import os
import sys
import itertools
import threading
import logging
from datetime import datetime
import os
import time
from .base import LLMProvider

logger = logging.getLogger(__name__)

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")


def safe_print(text: str, prefix: str = "", suffix: str = ""):
    try:
        print(f"{prefix}{text}{suffix}", flush=True)
    except UnicodeEncodeError:
        try:
            encoding = sys.stdout.encoding or "utf-8"
            safe_text = text.encode(encoding, errors="replace").decode(encoding)
            print(f"{prefix}{safe_text}{suffix}", flush=True)
        except Exception:
            pass

# ---------------------------------------------------------------------------
# Key pool — parse once at import time, rotate at runtime
# ---------------------------------------------------------------------------

def _parse_api_keys() -> list[str]:
    """Parse GEMINI_API_KEY from the environment.

    Supports a single key or a comma-separated list:
        GEMINI_API_KEY=key1,key2,key3
    Returns a list preserving insertion order, stripping whitespace.
    """
    raw = os.environ.get("GEMINI_API_KEY", "")
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    if len(keys) > 1:
        logger.info(
            "Gemini key pool: %d key(s) loaded — round-robin request rotation active.", len(keys)
        )
    return keys


_KEY_POOL: list[str] = _parse_api_keys()
_KEY_CYCLE = itertools.cycle(_KEY_POOL) if _KEY_POOL else None
_KEY_LOCK = threading.Lock()  # thread-safe under uvicorn workers
_REQUEST_LOCK = threading.Lock()

# Simple in-process token bucket to avoid exceeding project RPM from this
# application instance. Configure via GEMINI_RPM_LIMIT in .env (default 5).
GEMINI_RPM_LIMIT = int(os.environ.get("GEMINI_RPM_LIMIT", "5"))
_TOKENS = GEMINI_RPM_LIMIT
_LAST_REFILL = time.time()
_TOKEN_LOCK = threading.Lock()

def _try_consume_token() -> bool:
    """Attempt to consume one token. Refill tokens every 60 seconds.

    This is an in-process limiter and won't coordinate across multiple
    processes — use Redis/file-lock for cross-process enforcement.
    """
    global _TOKENS, _LAST_REFILL
    now = time.time()
    with _TOKEN_LOCK:
        # refill once per minute proportional to elapsed time
        elapsed = now - _LAST_REFILL
        if elapsed >= 60:
            # refill fully each minute
            _TOKENS = GEMINI_RPM_LIMIT
            _LAST_REFILL = now
        if _TOKENS > 0:
            _TOKENS -= 1
            return True
        return False


def _next_api_key() -> str | None:
    """Return the next API key from the pool (round-robin, thread-safe)."""
    if _KEY_CYCLE is None:
        return None
    with _KEY_LOCK:
        return next(_KEY_CYCLE)


def _is_quota_error(exc: Exception) -> bool:
    """Return True if the exception is a Gemini quota/rate-limit error (HTTP 429).
    Must NOT match 404 model-not-found errors (which contain 'generateContent')."""
    msg = str(exc).lower()
    # Exclude 404s explicitly — those are model-not-found, not quota issues
    if "404" in msg and "not found" in msg:
        return False
    return "429" in str(exc) or "quota" in msg or "resource_exhausted" in msg or "rate limit" in msg


# ---------------------------------------------------------------------------
# Provider class
# ---------------------------------------------------------------------------

class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        # If an explicit key is passed (e.g. in tests), use it always.
        # Otherwise keys come from the rotation pool.
        self._explicit_key = api_key
        self.model = model or GEMINI_MODEL
        if not self._explicit_key and not _KEY_POOL:
            raise RuntimeError(
                "GEMINI_API_KEY is not set — get one at https://aistudio.google.com/apikey"
            )

    def complete(self, system: str, user: str, image_path: str = None, max_tokens: int | None = None) -> str:
        import google.generativeai as genai
        from .ollama_client import OllamaProvider
        # If local rate limiter says we've exhausted our RPM budget, fall
        # back to Ollama immediately to avoid sending a request that will
        # be rejected by Gemini and to prevent further quota consumption.
        if not _try_consume_token():
            logger.warning("Gemini local RPM limit reached — falling back to Ollama for this request.")
            return OllamaProvider().complete(system, user, image_path, max_tokens)

        # If an explicit key was provided at construction time, just use it always.
        # (single-attempt only; no retry with a different key.)
        if self._explicit_key:
            return self._attempt(genai, system, user, self._explicit_key, image_path, max_tokens)

        # One key per request, rotate keys round-robin across requests.
        with _REQUEST_LOCK:
            api_key = _next_api_key()
            key_hint = f"...{api_key[-6:]}" if api_key else "none"
            try:
                return self._attempt(genai, system, user, api_key, image_path, max_tokens)
            except Exception as exc:
                logger.error(
                    "Gemini request failed (key=%s): %s.",
                    key_hint, exc,
                )
                self._log_error_to_db(exc, key_hint, system, error_type="api")
                raise exc


    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _attempt(self, genai, system: str, user: str, api_key: str, image_path: str = None, max_tokens: int | None = None) -> str:
        """Make a single Gemini API call with the given key. Raises on failure."""
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(self.model, system_instruction=system)
        # Try to read the executor thread-local request id if set by the
        # backend's mcp_client so logs can correlate calls to a pipeline run.
        req_id = None
        try:
            # Importing here avoids circular imports at module load time.
            from usisain_backend.services.mcp_client.client import _EXEC_CTX
            req_id = getattr(_EXEC_CTX, "request_id", None)
        except Exception:
            req_id = None

        # Build a metadata prefix with timestamp, pid, thread id, and request id
        now = datetime.utcnow().isoformat(timespec='milliseconds')
        pid = os.getpid()
        tid = threading.get_ident()
        rid_msg = f" request_id={req_id}" if req_id else ""
        meta = f"{now} PID:{pid} TID:{tid}{rid_msg}"
        prefix = "\nINFO:     "
        safe_print(f"[Gemini LLM Call] Model: {self.model} {meta}", prefix=prefix)
        safe_print("--- GEMINI SYSTEM PROMPT ---", prefix="INFO:     ")
        safe_print(system)
        safe_print("--- GEMINI USER PROMPT ---", prefix="INFO:     ")
        safe_print(user)
        if image_path:
            safe_print("--- GEMINI ATTACHED IMAGE ---", prefix="INFO:     ")
            safe_print(image_path)
        # Also include a short caller stack to help identify duplicate calls
        try:
            import traceback as _tb
            stack = "".join(_tb.format_stack(limit=6))
            safe_print(f"--- CALLER STACK --- {meta}", prefix="INFO:     ")
            safe_print(stack, prefix="INFO:     ")
        except Exception:
            pass
        safe_print("-----------------------------", prefix="INFO:     ", suffix="\n")

        contents = []
        if image_path and os.path.exists(image_path):
            try:
                from PIL import Image
                from io import BytesIO
                # Open image and downsample/compress if large to reduce upload
                img = Image.open(image_path)
                width, height = img.size
                file_size = None
                try:
                    file_size = os.path.getsize(image_path)
                except Exception:
                    file_size = None

                need_resize = False
                MAX_DIM = 1024
                MAX_BYTES = 200 * 1024  # 200 KB
                if width > MAX_DIM or height > MAX_DIM:
                    need_resize = True
                if file_size and file_size > MAX_BYTES:
                    need_resize = True

                if need_resize:
                    try:
                        img = img.convert("RGB")
                        img.thumbnail((MAX_DIM, MAX_DIM), Image.LANCZOS)
                        buf = BytesIO()
                        img.save(buf, format="JPEG", quality=75)
                        buf.seek(0)
                        img = Image.open(buf)
                    except Exception as e:
                        logger.warning("Could not resize/compress image for Gemini: %s", e)

                contents.append(img)
            except Exception as e:
                logger.warning("Could not open image for Gemini multimodal: %s", e)
                
        contents.append(user)
        config = {}
        if max_tokens is not None:
            config["max_output_tokens"] = max_tokens
        response = model.generate_content(
            contents,
            generation_config=genai.GenerationConfig(**config) if config else None,
            request_options={"timeout": 120.0}
        )
        return response.text.strip()


    def _log_error_to_db(self, exc: Exception, key_hint: str,
                         system: str, error_type: str = "api") -> None:
        """Silently log the error to the database (best-effort)."""
        try:
            from usisain_backend.data import db
            db.insert_error(
                step=None,
                step_name="gemini_client",
                error_msg=f"Gemini API call failed: {exc}",
                error_type=error_type,
                details=f"Model: {self.model}\nKey hint: {key_hint}\nSystem: {system}",
            )
        except Exception as db_err:
            logger.warning("Could not log Gemini error to database: %s", db_err)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_provider(preference: str = "ollama") -> LLMProvider:
    """Return the requested LLM provider.

    'gemini' — GeminiProvider with automatic key rotation and quota retry.
               Falls back silently to Ollama if no API key is configured.
    'ollama' — local Ollama (default).
    """
    selected = (preference or "ollama").strip().lower()
    if selected == "gemini" and _KEY_POOL:
        return GeminiProvider()
    from .ollama_client import OllamaProvider
    return OllamaProvider()
