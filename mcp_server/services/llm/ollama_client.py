"""ollama_client.py — local LLM provider via Ollama. This is the default
provider: fully offline, no API key, no data leaves the machine.

Model selection is automatic:
  - Text-only prompts  → OLLAMA_MODEL        (default: llama3.2:1b)
  - Image/vision prompts → OLLAMA_VISION_MODEL (default: moondream)
"""

import os
import sys
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
    """Quick non-blocking check whether Ollama service is reachable."""
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
        self.text_model = model or OLLAMA_MODEL
        self.vision_model = OLLAMA_VISION_MODEL
        self.client = _get_ollama_client(host)

    async def complete(self, system: str, user: str, image_path: str = None, max_tokens: int | None = None) -> str:
        needs_vision = image_path and os.path.exists(image_path)

        # Pick the right model based on whether we have an image
        active_model = self.vision_model if needs_vision else self.text_model

        # Print the prompt details to the terminal
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

        message = {"role": "user", "content": user}
        if needs_vision:
            message["images"] = [image_path]

        options = {
            "temperature": 0.2,
            "top_p": 0.9,
        }
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        else:
            options["num_predict"] = 256 if not needs_vision else 384

        response = await self.client.chat(
            model=active_model,
            messages=[
                {"role": "system", "content": system},
                message,
            ],
            options=options,
        )

        return response.message.content.strip()
