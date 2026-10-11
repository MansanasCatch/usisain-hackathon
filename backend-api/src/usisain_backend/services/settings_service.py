import os
import socket
from typing import Any

from dotenv import load_dotenv

from mcp_server.services.llm.key_pool import mask_key
from mcp_server.shared.ocr_utils import is_ocr_available
from usisain_backend.core.config import settings


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_ai_settings() -> dict[str, Any]:
    load_dotenv(settings.project_root / ".env", override=True)
    gem_key = os.environ.get("GEMINI_API_KEY", "")
    grok_key = os.environ.get("GROK_API_KEY", "")
    return {
        "default_provider": os.environ.get("DEFAULT_LLM_PROVIDER", "ollama"),
        "ocr_available": is_ocr_available(),
        "gemini": {
            "has_key": bool(gem_key.strip()),
            "key_masked": mask_key(gem_key),
            "model": os.environ.get("GEMINI_MODEL", "gemini-3.5-flash"),
            "available_models": [
                "gemini-2.5-flash",
                "gemini-2.5-pro",
                "gemini-2.0-flash",
                "gemini-2.0-pro-exp-02-05",
                "gemini-1.5-flash",
                "gemini-1.5-pro",
            ],
        },
        "grok": {
            "has_key": bool(grok_key.strip()),
            "key_masked": mask_key(grok_key),
            "model": os.environ.get("GROK_MODEL", "gpt-oss-120b"),
            "available_models": [
                "gpt-oss-120b",
                "grok-4.1-fast",
                "grok-4.7",
                "grok-4.6",
                "grok-4.5",
                "grok-4.3",
                "grok-4.20-reasoning",
                "grok-beta",
                "grok-2-vision-1212",
            ],
        },
        "ollama": {
            "model": os.environ.get("OLLAMA_MODEL", "llama3.2:1b"),
            "vision_model": os.environ.get("OLLAMA_VISION_MODEL", "moondream"),
            "host": os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
        },
    }


def update_ai_settings(
    default_provider: str | None = None,
    gemini_api_key: str | None = None,
    gemini_model: str | None = None,
    grok_api_key: str | None = None,
    grok_model: str | None = None,
    ollama_model: str | None = None,
    ollama_vision_model: str | None = None,
) -> dict[str, Any]:
    if default_provider is not None:
        p = default_provider.strip().lower()
        if p in ("ollama", "gemini", "grok"):
            settings.persist_env_var("DEFAULT_LLM_PROVIDER", p)
    if gemini_api_key is not None:
        settings.persist_env_var("GEMINI_API_KEY", gemini_api_key)
    if gemini_model is not None and gemini_model.strip():
        settings.persist_env_var("GEMINI_MODEL", gemini_model)
    if grok_api_key is not None:
        settings.persist_env_var("GROK_API_KEY", grok_api_key)
    if grok_model is not None and grok_model.strip():
        settings.persist_env_var("GROK_MODEL", grok_model)
    if ollama_model is not None and ollama_model.strip():
        settings.persist_env_var("OLLAMA_MODEL", ollama_model)
    if ollama_vision_model is not None and ollama_vision_model.strip():
        settings.persist_env_var("OLLAMA_VISION_MODEL", ollama_vision_model)
    return {"status": "ok", "settings": get_ai_settings()}


def test_api_key(provider: str, api_key: str | None = None) -> dict[str, Any]:
    p = provider.strip().lower()
    if p == "gemini":
        from mcp_server.services.llm.gemini_client import GeminiProvider

        try:
            prov = GeminiProvider(api_key=api_key)
            import asyncio

            asyncio.run(prov.complete("Say ok", "test", max_tokens=5))
            return {
                "status": "ok",
                "message": "Gemini API key is valid and connected successfully.",
            }
        except Exception as e:
            return {"status": "error", "message": f"Gemini test failed: {e}"}
    elif p == "grok":
        from mcp_server.services.llm.grok_client import GrokProvider

        try:
            prov = GrokProvider(api_key=api_key)
            import asyncio

            asyncio.run(prov.complete("Say ok", "test", max_tokens=5))
            return {"status": "ok", "message": "Grok API key is valid and connected successfully."}
        except Exception as e:
            return {"status": "error", "message": f"Grok test failed: {e}"}
    return {"status": "error", "message": f"Unknown provider: {provider}"}


def list_ollama_models() -> dict[str, Any]:
    import ollama

    active_model = os.environ.get("OLLAMA_MODEL", "llama3.2:1b")
    active_vision = os.environ.get("OLLAMA_VISION_MODEL", "moondream")
    models_out = []
    try:
        client = ollama.Client(host=settings.ollama_host)
        raw = client.list()
        items = getattr(raw, "models", [])
        if isinstance(raw, dict) and "models" in raw:
            items = raw["models"]
        elif isinstance(raw, list):
            items = raw
        for m in items:
            name = getattr(m, "model", None) or (m.get("model") if isinstance(m, dict) else str(m))
            size = getattr(m, "size", None) or (m.get("size", 0) if isinstance(m, dict) else 0)
            modified_at = getattr(m, "modified_at", None) or (
                m.get("modified_at") if isinstance(m, dict) else None
            )
            if modified_at and (not isinstance(modified_at, str)):
                try:
                    modified_at = modified_at.isoformat()
                except Exception:
                    modified_at = str(modified_at)
            models_out.append(
                {
                    "name": str(name).strip(),
                    "size_bytes": int(size or 0),
                    "modified_at": str(modified_at or ""),
                }
            )
    except Exception:
        pass
    return {
        "models": models_out,
        "active_model": active_model,
        "active_vision_model": active_vision,
    }


def list_grok_models() -> dict[str, Any]:
    from mcp_server.services.llm.grok_client import list_grok_models as _list_grok

    try:
        models = _list_grok()
        return {"status": "ok", "models": models}
    except Exception as e:
        return {
            "status": "ok",
            "models": [
                "gpt-oss-120b",
                "grok-4.1-fast",
                "grok-4.7",
                "grok-4.6",
                "grok-4.5",
                "grok-4.3",
                "grok-4.20-reasoning",
                "grok-beta",
                "grok-2-vision-1212",
            ],
            "fallback": True,
            "error": str(e),
        }
