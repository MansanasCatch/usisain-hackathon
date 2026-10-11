"""grok_client.py — optional cloud LLM provider (xAI Grok).

Provides high-speed reasoning and vision analysis via xAI's OpenAI-compatible API.
Get an API key at https://console.x.ai/

Runtime configuration
---------------------
The API key(s) and model are read from the environment on every request, so
changing them from the dashboard's AI Settings panel takes effect
immediately — no restart needed.

API Key Rotation & round-robin request usage
---------------------------------------------
Set GROK_API_KEY to a comma-separated list of keys to enable automatic
round-robin rotation across requests:

    GROK_API_KEY=key1,key2,key3

Behaviour on errors:
    1. Each request starts on the next key in the pool.
    2. Quota (429) / auth errors retry on the next key in the pool.
    3. Any unrecoverable error is raised so the factory falls back to Ollama.
"""

import os
import sys
import base64
import logging
import threading
import asyncio
import importlib
from pathlib import Path
from datetime import datetime, timezone
from io import BytesIO
import requests
from PIL import Image

# Ensure backend-api/src is discoverable if running inside the repository
_backend_src = str(Path(__file__).resolve().parents[3] / "backend-api" / "src")
if _backend_src not in sys.path and os.path.exists(_backend_src):
    sys.path.insert(0, _backend_src)

from .base import LLMProvider
from .key_pool import KeyPool, mask_key

logger = logging.getLogger(__name__)

DEFAULT_GROK_MODEL = "gpt-oss-120b"
GROK_API_URL = "https://api.x.ai/v1/chat/completions"
GROK_MODELS_URL = "https://api.x.ai/v1/models"
GROK_REQUEST_TIMEOUT = 120.0

KEY_POOL = KeyPool("GROK_API_KEY")


def _get_request_id() -> str | None:
    """Safely obtain current request ID from execution context if running under backend."""
    try:
        mod = sys.modules.get("usisain_backend.services.mcp_client.client")
        if not mod:
            mod = importlib.import_module("usisain_backend.services.mcp_client.client")
        ctx = getattr(mod, "_EXEC_CTX", None)
        return getattr(ctx, "request_id", None) if ctx else None
    except Exception:
        return None


def current_model() -> str:
    """Active Grok model — read live so runtime switches apply instantly."""
    return (os.environ.get("GROK_MODEL") or DEFAULT_GROK_MODEL).strip()


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


def _is_quota_error(status_code: int, msg: str) -> bool:
    return status_code == 429 or "rate_limit" in msg or "quota" in msg or "resource_exhausted" in msg


def _is_auth_error(status_code: int, msg: str) -> bool:
    return status_code in (401, 403) or any(
        term in msg for term in ("unauthorized", "invalid_api_key", "permission_denied", "forbidden")
    )


def _encode_image_b64(image_path: str) -> str | None:
    """Read, downsample if needed, and base64-encode image for vision API."""
    try:
        img = Image.open(image_path)
        max_dim = 1024
        max_bytes = 250 * 1024  # 250 KB
        try:
            file_size = os.path.getsize(image_path)
        except OSError:
            file_size = 0

        if img.width > max_dim or img.height > max_dim or file_size > max_bytes:
            img = img.convert("RGB")
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=80)
            data = buf.getvalue()
        else:
            with open(image_path, "rb") as f:
                data = f.read()

        return f"data:image/jpeg;base64,{base64.b64encode(data).decode('utf-8')}"
    except Exception as e:
        logger.warning("Could not encode image for Grok vision: %s", e)
        return None


class GrokProvider(LLMProvider):
    name = "grok"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._explicit_key = (api_key or "").strip() or None
        self.model = (model or "").strip() or current_model()
        if not self._explicit_key and not KEY_POOL.has_keys():
            raise RuntimeError(
                "GROK_API_KEY is not set — add one in Dashboard → AI Settings "
                "or get one at https://console.x.ai/"
            )

    async def complete(self, system: str, user: str, image_path: str = None, max_tokens: int | None = None) -> str:
        if self._explicit_key:
            try:
                return await asyncio.to_thread(self._attempt_sync, system, user, self._explicit_key, image_path, max_tokens)
            except Exception as exc:
                self._log_error_to_db(exc, mask_key(self._explicit_key), system)
                raise

        max_attempts = max(1, len(KEY_POOL.keys()))
        last_exc: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            api_key = KEY_POOL.next_key()
            if not api_key:
                raise RuntimeError("No Grok API keys configured")
            key_hint = mask_key(api_key)
            try:
                return await asyncio.to_thread(self._attempt_sync, system, user, api_key, image_path, max_tokens)
            except Exception as exc:
                last_exc = exc
                logger.error("Grok request failed (key=%s, attempt %d/%d): %s", key_hint, attempt, max_attempts, exc)
                self._log_error_to_db(exc, key_hint, system)

                err_str = str(exc).lower()
                status = getattr(exc, "status_code", 0)
                if (_is_quota_error(status, err_str) or _is_auth_error(status, err_str)) and attempt < max_attempts:
                    logger.warning("Quota/auth error on Grok key — retrying with the next key in the pool...")
                    continue
                raise
        raise last_exc or RuntimeError("Grok request failed")

    def _attempt_sync(self, system: str, user: str, api_key: str, image_path: str = None, max_tokens: int | None = None) -> str:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # Correlate logs with request id if available
        req_id = _get_request_id()

        now = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        rid_msg = f" request_id={req_id}" if req_id else ""
        meta = f"{now} PID:{os.getpid()} TID:{threading.get_ident()}{rid_msg}"
        safe_print(f"[Grok LLM Call] Model: {self.model} {meta}", prefix="\nINFO:     ")
        if os.environ.get("USISAIN_DEBUG_PROMPTS", "0").lower() in ("1", "true", "yes"):
            safe_print("--- GROK SYSTEM PROMPT ---", prefix="INFO:     ")
            safe_print(system)
            safe_print("--- GROK USER PROMPT ---", prefix="INFO:     ")
            safe_print(user)
            if image_path:
                safe_print("--- GROK ATTACHED IMAGE ---", prefix="INFO:     ")
                safe_print(image_path)
            safe_print("-----------------------------", prefix="INFO:     ", suffix="\n")

        messages = []
        if system:
            messages.append({"role": "system", "content": system})

        if image_path and os.path.exists(image_path):
            img_b64 = _encode_image_b64(image_path)
            if img_b64:
                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user or ""},
                        {"type": "image_url", "image_url": {"url": img_b64}},
                    ]
                })
            else:
                messages.append({"role": "user", "content": user or ""})
        else:
            messages.append({"role": "user", "content": user or ""})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        resp = requests.post(GROK_API_URL, headers=headers, json=payload, timeout=GROK_REQUEST_TIMEOUT)
        if resp.status_code != 200:
            err_msg = f"Grok API returned HTTP {resp.status_code}: {resp.text}"
            exc = RuntimeError(err_msg)
            setattr(exc, "status_code", resp.status_code)
            raise exc

        try:
            data = resp.json()
        except Exception as json_err:
            raise RuntimeError(f"Grok API returned non-JSON response (HTTP {resp.status_code}): {resp.text}") from json_err

        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError(f"Grok API returned no completions: {data}")

        message_obj = choices[0].get("message", {})
        content = message_obj.get("content", "")
        return (content or "").strip()

    def _log_error_to_db(self, exc: Exception, key_hint: str, system: str) -> None:
        try:
            db_mod = sys.modules.get("usisain_backend.data.db")
            if not db_mod:
                db_mod = importlib.import_module("usisain_backend.data.db")
            db_mod.insert_error(
                step=None,
                step_name="grok_client",
                error_msg=f"Grok API call failed: {exc}",
                error_type="api",
                details=f"Model: {self.model}\nKey hint: {key_hint}\nSystem: {system}",
            )
        except Exception as db_err:
            logger.warning("Could not log Grok error to database: %s", db_err)


def list_models(api_key: str | None = None) -> list[str]:
    """Return available Grok models. Raises on failure."""
    key = (api_key or "").strip() or KEY_POOL.next_key()
    if not key:
        raise RuntimeError("GROK_API_KEY is not set")

    headers = {"Authorization": f"Bearer {key}"}
    resp = requests.get(GROK_MODELS_URL, headers=headers, timeout=10.0)
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to fetch Grok models: HTTP {resp.status_code} {resp.text}")

    data = resp.json()
    items = data.get("data", [])
    model_ids = [m["id"] for m in items if isinstance(m, dict) and "id" in m]
    return sorted(model_ids) if model_ids else [DEFAULT_GROK_MODEL]
