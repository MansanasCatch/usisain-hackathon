"""gemini_client.py — optional cloud LLM provider (Google Gemini). Use this
when you want stronger reasoning than a small local model can reliably give,
at the cost of that content leaving the machine. Get a free API key at
https://aistudio.google.com/apikey

Runtime configuration
---------------------
The API key(s) and model are read from the environment on every request, so
changing them from the dashboard's AI Settings panel takes effect
immediately — no restart needed.

API Key Rotation & round-robin request usage
---------------------------------------------
Set GEMINI_API_KEY to a comma-separated list of keys to enable automatic
round-robin rotation across requests.

    GEMINI_API_KEY=key1,key2,key3

Behaviour on errors:
    1. Each request starts on the next key in the pool.
    2. Quota (429) / auth errors retry on the next key in the pool.
    3. Any other error (network, timeout, invalid prompt) is raised
       immediately — the provider factory (factory.py) then falls back to
       the local Ollama provider so the pipeline never dead-ends.
"""

import asyncio
import importlib
import logging
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

_backend_src = str(Path(__file__).resolve().parents[3] / "backend-api" / "src")
if _backend_src not in sys.path and os.path.exists(_backend_src):
    sys.path.insert(0, _backend_src)
from .base import LLMProvider
from .key_pool import KeyPool, mask_key

logger = logging.getLogger(__name__)
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"
GEMINI_REQUEST_TIMEOUT = 120.0
KEY_POOL = KeyPool("GEMINI_API_KEY")


def _get_request_id() -> str | None:
    try:
        mod = sys.modules.get("usisain_backend.services.mcp_client.client")
        if not mod:
            mod = importlib.import_module("usisain_backend.services.mcp_client.client")
        ctx = getattr(mod, "_EXEC_CTX", None)
        return getattr(ctx, "request_id", None) if ctx else None
    except Exception:
        return None


def current_model() -> str:
    return (os.environ.get("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL).strip()


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


_TOKEN_LOCK = threading.Lock()
_TOKENS: float | None = None
_LAST_REFILL = time.time()


def _rpm_limit() -> int:
    try:
        per_key = int(os.environ.get("GEMINI_RPM_LIMIT", "15"))
    except ValueError:
        per_key = 15
    return max(1, per_key) * max(1, len(KEY_POOL.keys()))


def _try_consume_token() -> bool:
    global _TOKENS, _LAST_REFILL
    now = time.time()
    limit = _rpm_limit()
    with _TOKEN_LOCK:
        if _TOKENS is None or now - _LAST_REFILL >= 60:
            _TOKENS = limit
            _LAST_REFILL = now
        _TOKENS = min(_TOKENS, limit)
        if _TOKENS > 0:
            _TOKENS -= 1
            return True
        return False


def _is_quota_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    if "404" in msg and "not found" in msg:
        return False
    return "429" in msg or "quota" in msg or "resource_exhausted" in msg or ("rate limit" in msg)


def _is_auth_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(
        (
            term in msg
            for term in ("api key", "invalid key", "403", "unauthorized", "permission", "blocked")
        )
    )


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._explicit_key = (api_key or "").strip() or None
        self.model = (model or "").strip() or current_model()
        if not self._explicit_key and (not KEY_POOL.has_keys()):
            raise RuntimeError(
                "GEMINI_API_KEY is not set — add one in Dashboard → AI Settings or get one at https://aistudio.google.com/apikey"
            )

    async def complete(
        self, system: str, user: str, image_path: str = None, max_tokens: int | None = None
    ) -> str:
        import google.generativeai as genai

        retry_delay = 2.0
        max_limit_retries = 5
        limit_retries = 0
        while not _try_consume_token():
            if limit_retries >= max_limit_retries:
                raise RuntimeError("Gemini local RPM limit reached")
            limit_retries += 1
            logger.warning(
                "Gemini local RPM limit reached. Sleeping %.1fs and retrying (attempt %d/%d)...",
                retry_delay,
                limit_retries,
                max_limit_retries,
            )
            await asyncio.sleep(retry_delay)
        if self._explicit_key:
            try:
                return await self._attempt(genai, system, user, self._explicit_key, image_path)
            except Exception as exc:
                self._log_error_to_db(exc, mask_key(self._explicit_key), system)
                raise
        max_attempts = max(1, len(KEY_POOL.keys()))
        last_exc: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            api_key = KEY_POOL.next_key()
            if not api_key:
                raise RuntimeError("No Gemini API keys configured")
            key_hint = mask_key(api_key)
            try:
                return await self._attempt(genai, system, user, api_key, image_path)
            except Exception as exc:
                last_exc = exc
                logger.error(
                    "Gemini request failed (key=%s, attempt %d/%d): %s",
                    key_hint,
                    attempt,
                    max_attempts,
                    exc,
                )
                self._log_error_to_db(exc, key_hint, system)
                if (_is_quota_error(exc) or _is_auth_error(exc)) and attempt < max_attempts:
                    logger.warning("Quota/auth error — retrying with the next key in the pool...")
                    continue
                raise
        raise last_exc or RuntimeError("Gemini request failed")

    async def _attempt(
        self, genai, system: str, user: str, api_key: str, image_path: str = None
    ) -> str:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(self.model, system_instruction=system)
        req_id = _get_request_id()
        now = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        rid_msg = f" request_id={req_id}" if req_id else ""
        meta = f"{now} PID:{os.getpid()} TID:{threading.get_ident()}{rid_msg}"
        safe_print(f"[Gemini LLM Call] Model: {self.model} {meta}", prefix="\nINFO:     ")
        if os.environ.get("USISAIN_DEBUG_PROMPTS", "0").lower() in ("1", "true", "yes"):
            safe_print("--- GEMINI SYSTEM PROMPT ---", prefix="INFO:     ")
            safe_print(system)
            safe_print("--- GEMINI USER PROMPT ---", prefix="INFO:     ")
            safe_print(user)
            if image_path:
                safe_print("--- GEMINI ATTACHED IMAGE ---", prefix="INFO:     ")
                safe_print(image_path)
            safe_print("-----------------------------", prefix="INFO:     ", suffix="\n")
        contents = []
        if image_path and os.path.exists(image_path):
            img = _load_image_for_upload(image_path)
            if img is not None:
                contents.append(img)
        contents.append(user)
        response = await model.generate_content_async(
            contents, request_options={"timeout": GEMINI_REQUEST_TIMEOUT}
        )
        return response.text.strip()

    def _log_error_to_db(self, exc: Exception, key_hint: str, system: str) -> None:
        try:
            db_mod = sys.modules.get("usisain_backend.data.db")
            if not db_mod:
                db_mod = importlib.import_module("usisain_backend.data.db")
            db_mod.insert_error(
                step=None,
                step_name="gemini_client",
                error_msg=f"Gemini API call failed: {exc}",
                error_type="api",
                details=f"Model: {self.model}\nKey hint: {key_hint}\nSystem: {system}",
            )
        except Exception as db_err:
            logger.warning("Could not log Gemini error to database: %s", db_err)


def _load_image_for_upload(image_path: str):
    try:
        from io import BytesIO

        from PIL import Image

        img = Image.open(image_path)
        max_dim = 1024
        max_bytes = 200 * 1024
        try:
            file_size = os.path.getsize(image_path)
        except OSError:
            file_size = 0
        if img.width > max_dim or img.height > max_dim or file_size > max_bytes:
            try:
                img = img.convert("RGB")
                img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
                buf = BytesIO()
                img.save(buf, format="JPEG", quality=75)
                buf.seek(0)
                img = Image.open(buf)
            except Exception as e:
                logger.warning("Could not resize/compress image for Gemini: %s", e)
        return img
    except Exception as e:
        logger.warning("Could not open image for Gemini multimodal: %s", e)
        return None


def list_models(api_key: str | None = None) -> list[str]:
    import google.generativeai as genai

    key = (api_key or "").strip() or KEY_POOL.next_key()
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    genai.configure(api_key=key)
    names = []
    for m in genai.list_models():
        methods = getattr(m, "supported_generation_methods", []) or []
        name = getattr(m, "name", "") or ""
        if "generateContent" in methods and name.startswith("models/gemini"):
            names.append(name.split("/", 1)[1])
    return sorted(set(names), reverse=True)


def get_provider(preference: str = "ollama") -> LLMProvider:
    from .factory import get_provider as _factory_get_provider

    return _factory_get_provider(preference)
