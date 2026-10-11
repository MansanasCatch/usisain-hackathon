import os
import socket
import threading
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
                "gemini-3.5-flash",
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
            "available_models": list_grok_models()["models"] if not grok_key.strip() else [m["name"] for m in list_grok_models().get("models", [])],
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


def is_ollama_online(timeout: float = 0.5) -> bool:
    import urllib.request

    host = settings.ollama_host.rstrip("/")
    probe_url = f"{host}/api/tags"
    try:
        req = urllib.request.Request(probe_url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout):
            return True
    except Exception:
        return False


_OLLAMA_PULL_LOCK = threading.Lock()
_OLLAMA_IS_PULLING = False
_OLLAMA_PULL_STATUS = ""


def start_pull_ollama_model(model_name: str = "llama3.2:1b") -> dict[str, Any]:
    global _OLLAMA_IS_PULLING, _OLLAMA_PULL_STATUS
    clean_model = model_name.strip() or "llama3.2:1b"
    with _OLLAMA_PULL_LOCK:
        if _OLLAMA_IS_PULLING:
            return {"status": "ok", "message": f"Already pulling {_OLLAMA_PULL_STATUS}"}
        _OLLAMA_IS_PULLING = True
        _OLLAMA_PULL_STATUS = f"Starting pull for {clean_model}..."

    def _worker():
        global _OLLAMA_IS_PULLING, _OLLAMA_PULL_STATUS
        try:
            import ollama

            client = ollama.Client(host=settings.ollama_host)
            _OLLAMA_PULL_STATUS = f"Connecting to Ollama registry for {clean_model}..."
            for progress in client.pull(clean_model, stream=True):
                status_str = (
                    getattr(progress, "status", None)
                    or (progress.get("status") if isinstance(progress, dict) else "")
                    or "downloading"
                )
                _OLLAMA_PULL_STATUS = f"Pulling {clean_model}: {status_str}"
            _OLLAMA_PULL_STATUS = f"Model {clean_model} is ready!"
        except Exception as e:
            _OLLAMA_PULL_STATUS = f"Pull failed: {e}"
        finally:
            _OLLAMA_IS_PULLING = False

    t = threading.Thread(target=_worker, daemon=True, name="ollama-pull-worker")
    t.start()
    return {"status": "ok", "message": f"Started pulling {clean_model} in background."}


def get_ollama_status() -> dict[str, Any]:
    global _OLLAMA_IS_PULLING, _OLLAMA_PULL_STATUS
    online = is_ollama_online()
    models_info = list_ollama_models() if online else {"models": []}
    models = models_info.get("models", [])
    default_model = os.environ.get("OLLAMA_MODEL", "llama3.2:1b")

    has_default = any(
        m.get("name", "").split(":")[0] == default_model.split(":")[0] for m in models
    )

    # Auto-trigger pull if Ollama is online, default model is missing, and not already pulling
    if online and not has_default and not _OLLAMA_IS_PULLING:
        start_pull_ollama_model(default_model)

    return {
        "online": online,
        "models": models,
        "default_model": default_model,
        "has_default_model": has_default,
        "is_pulling": _OLLAMA_IS_PULLING,
        "pull_status": _OLLAMA_PULL_STATUS,
    }


def list_ollama_models() -> dict[str, Any]:
    import ollama

    active_model = os.environ.get("OLLAMA_MODEL", "llama3.2:1b")
    active_vision = os.environ.get("OLLAMA_VISION_MODEL", "moondream")
    models_out = []
    online = False
    try:
        client = ollama.Client(host=settings.ollama_host)
        raw = client.list()
        online = True
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
            from mcp_server.shared.model_utils import model_supports_vision

            m_name = str(name).strip()
            s_vis = model_supports_vision("ollama", m_name)
            models_out.append(
                {
                    "name": m_name,
                    "size_bytes": int(size or 0),
                    "modified_at": str(modified_at or ""),
                    "supports_vision": s_vis,
                    "capability": "Vision + Text" if s_vis else "Text Only",
                }
            )
    except Exception:
        pass
    return {
        "online": online,
        "models": models_out,
        "active_model": active_model,
        "active_vision_model": active_vision,
        "is_pulling": _OLLAMA_IS_PULLING,
        "pull_status": _OLLAMA_PULL_STATUS,
    }


def list_grok_models() -> dict[str, Any]:
    from mcp_server.shared.model_utils import model_supports_vision

    default_models = [
        {
            "name": "gpt-oss-120b",
            "description": "High-capacity reasoning & open-weight architecture (Recommended)",
            "supports_vision": False,
            "capability": "Text Only",
        },
        {
            "name": "grok-4.1-fast",
            "description": "High-speed, cost-efficient reasoning & chat",
            "supports_vision": False,
            "capability": "Text Only",
        },
        {
            "name": "grok-4.7",
            "description": "Flagship high-capability model",
            "supports_vision": False,
            "capability": "Text Only",
        },
        {
            "name": "grok-4.6",
            "description": "Advanced reasoning model",
            "supports_vision": False,
            "capability": "Text Only",
        },
        {
            "name": "grok-4.5",
            "description": "High-performance general model",
            "supports_vision": False,
            "capability": "Text Only",
        },
        {
            "name": "grok-4.3",
            "description": "Long-context reasoning",
            "supports_vision": False,
            "capability": "Text Only",
        },
        {
            "name": "grok-4.20-reasoning",
            "description": "Specialized deep reasoning model",
            "supports_vision": False,
            "capability": "Text Only",
        },
        {
            "name": "grok-beta",
            "description": "Public beta preview",
            "supports_vision": False,
            "capability": "Text Only",
        },
        {
            "name": "grok-2-vision-1212",
            "description": "Dedicated multimodal vision model",
            "supports_vision": True,
            "capability": "Vision + Text",
        },
    ]
    from mcp_server.services.llm.grok_client import KEY_POOL, current_model, list_models

    if KEY_POOL.has_keys():
        try:
            live = list_models()
            models_out = [
                {
                    "name": m,
                    "description": "xAI Model" if not m.startswith("openai/") and "llama" not in m else "Cloud LLM",
                    "supports_vision": model_supports_vision("grok", m),
                    "capability": "Vision + Text" if model_supports_vision("grok", m) else "Text Only",
                }
                for m in live
            ]
            return {"models": models_out, "active_model": current_model()}
        except Exception:
            pass
    return {"models": default_models, "active_model": current_model()}
