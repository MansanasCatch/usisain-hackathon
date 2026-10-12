import os
import sys
from typing import Any

import ollama

from .base import LLMProvider

OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:1b")
OLLAMA_VISION_MODEL = os.environ.get("OLLAMA_VISION_MODEL", "moondream")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_CLIENT_TIMEOUT = float(os.environ.get("OLLAMA_CLIENT_TIMEOUT", "120.0"))
DEBUG_OLLAMA_PROMPTS = os.environ.get("USISAIN_DEBUG_PROMPTS", "0").lower() in ("1", "true", "yes")
_OLLAMA_CLIENT = None


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


def _get_ollama_client(host: str | None = None):
    global _OLLAMA_CLIENT
    if _OLLAMA_CLIENT is None:
        _OLLAMA_CLIENT = ollama.AsyncClient(host=host or OLLAMA_HOST, timeout=OLLAMA_CLIENT_TIMEOUT)
    return _OLLAMA_CLIENT


def is_ollama_available(timeout: float = 1.0) -> bool:
    try:
        import urllib.request

        host = (os.environ.get("OLLAMA_HOST") or "http://localhost:11434").rstrip("/")
        req = urllib.request.Request(f"{host}/api/tags", headers={"User-Agent": "UsisAIn-Check"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, model: str | None = None, host: str | None = None):
        self._model = model
        self.client = _get_ollama_client(host)

    @property
    def text_model(self) -> str:
        model = self._model or os.environ.get("OLLAMA_MODEL", "llama3.2:1b")
        if "moondream" in model.lower() or "vision" in model.lower():
            return "llama3.2:1b"
        return model

    @property
    def vision_model(self) -> str:
        model = os.environ.get("OLLAMA_VISION_MODEL", "moondream")
        if "llama3.2-vision" in model.lower():
            return "moondream"
        return model

    async def complete(
        self, system: str, user: str, image_path: str | None = None, max_tokens: int | None = None
    ) -> str:
        needs_vision = bool(image_path and os.path.exists(image_path))
        active_model = self.vision_model if needs_vision else self.text_model
        safe_print(f"[Ollama LLM Call] Model: {active_model}", prefix="\nINFO:     ")
        if DEBUG_OLLAMA_PROMPTS:
            safe_print("--- OLLAMA SYSTEM PROMPT ---", prefix="INFO:     ")
            safe_print(system)
            safe_print("--- OLLAMA USER PROMPT ---", prefix="INFO:     ")
            safe_print(user)
            if image_path:
                safe_print("--- OLLAMA ATTACHED IMAGE ---", prefix="INFO:     ")
                safe_print(image_path)
            safe_print("-----------------------------", prefix="INFO:     ", suffix="\n")
        message: dict[str, Any] = {"role": "user", "content": user}
        if needs_vision:
            message["images"] = [image_path]
        options = {"temperature": 0.2, "top_p": 0.9}
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        else:
            options["num_predict"] = 256 if not needs_vision else 384
        try:
            response = await self.client.chat(
                model=active_model,
                messages=[{"role": "system", "content": system}, message],
                options=options,
            )
            content = response.message.content
            return (content or "").strip()
        except Exception as e:
            err_msg = str(e).lower()
            if "compatible" in err_msg or "not found" in err_msg or "pull" in err_msg:
                fallback = "moondream" if needs_vision else "llama3.2:1b"
                if active_model != fallback:
                    safe_print(
                        f"[Ollama Fallback] Model '{active_model}' failed: {e}. Retrying with '{fallback}'...",
                        prefix="\nWARNING:  ",
                    )
                    retry_resp = await self.client.chat(
                        model=fallback,
                        messages=[{"role": "system", "content": system}, message],
                        options=options,
                    )
                    content = retry_resp.message.content
                    return (content or "").strip()
            raise
