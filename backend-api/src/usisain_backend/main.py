"""main.py — entrypoint. Run with:
    uvicorn usisain_backend.main:app --reload --app-dir src --port 8000
(from inside backend-api/, with the venv active)
Reload triggered 9.
"""

import os
import sys
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from usisain_backend.core.logging import setup_logging
from usisain_backend.core.config import settings
from usisain_backend.data import db
from usisain_backend.api import stream, analyze, scans, tts, reference_docs, errors

setup_logging()
logger = logging.getLogger(__name__)

if str(settings.project_root) not in sys.path:
    sys.path.insert(0, str(settings.project_root))
_mcp_server_root = settings.project_root / "mcp_server"
if str(_mcp_server_root) not in sys.path:
    sys.path.insert(0, str(_mcp_server_root))

OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:1b")
OLLAMA_VISION_MODEL = os.environ.get("OLLAMA_VISION_MODEL", "moondream")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")


def _ensure_ollama_model(model_name: str) -> bool:
    """Check that Ollama is reachable and the given model is pulled.
    Returns True if Ollama is running and model is ready, False otherwise."""
    model_name = model_name.strip()
    host_name = OLLAMA_HOST.strip()

    try:
        import ollama
    except ImportError:
        logger.warning("ollama package not installed — skipping model check")
        return False

    client = ollama.Client(host=host_name)

    # 1. Check connectivity
    try:
        models = client.list()
    except Exception as e:
        logger.warning(
            "[Ollama] Cannot reach Ollama at %s -- is it running? Error: %s",
            host_name, e,
        )
        return False

    # 2. Check if model is already available (handle both ListResponse object, list, or dict)
    available = []
    if hasattr(models, "models"):
        available = [m.model for m in models.models]
    elif isinstance(models, dict) and "models" in models:
        available = [m.get("model", m.get("name", "")) for m in models["models"]]
    elif isinstance(models, list):
        available = [m.model if hasattr(m, "model") else m.get("model", "") for m in models]
    else:
        # Fallback
        available = [getattr(m, "model", str(m)) for m in getattr(models, "models", [])]

    model_present = False
    for name in available:
        name_clean = name.strip()
        if model_name == name_clean or model_name.split(":")[0] == name_clean.split(":")[0]:
            model_present = True
            break

    if model_present:
        logger.info("[Ollama] Model '%s' is ready", model_name)
        return True

    # 3. Auto-pull the model
    logger.info("[Ollama] Model '%s' not found locally -- pulling now (this may take a while on first run)...", model_name)
    try:
        current_digest = None
        last_logged_pct = -10
        for progress in client.pull(model_name, stream=True):
            status = progress.get("status", "")
            digest = progress.get("digest", "")
            completed = progress.get("completed", 0)
            total = progress.get("total", 0)
            
            if digest != current_digest:
                current_digest = digest
                if status:
                    logger.info("[Ollama] Pull: %s %s", status, digest[:12] if digest else "")
            elif total > 0:
                pct = int(completed / total * 100)
                if pct % 10 == 0 and pct != last_logged_pct:
                    last_logged_pct = pct
                    logger.info("[Ollama] Pull progress for '%s': %d%% completed", model_name, pct)
                    
        logger.info("[Ollama] Successfully pulled '%s'", model_name)
        return True
    except Exception as e:
        logger.error("[Ollama] Failed to pull model '%s': %s", model_name, e)
        return False


def _auto_configure_fallback_ai():
    """When Ollama is unavailable or not installed, automatically look for
    an alternative AI model in .env that has an API key configured and make
    it the default AI and model."""
    from dotenv import load_dotenv
    load_dotenv(settings.project_root / ".env", override=True)

    grok_key = os.environ.get("GROK_API_KEY", "").strip()
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()

    chosen_provider = None
    chosen_model = None

    # Check for Grok first (default: gpt-oss-120b)
    if grok_key:
        chosen_provider = "grok"
        chosen_model = os.environ.get("GROK_MODEL", "gpt-oss-120b").strip()
    elif gemini_key:
        chosen_provider = "gemini"
        chosen_model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash").strip()

    if chosen_provider and chosen_model:
        os.environ["DEFAULT_LLM_PROVIDER"] = chosen_provider
        settings.default_llm_provider = chosen_provider
        logger.warning(
            "[AI Auto-Detect] Ollama is not running/installed. "
            "Found active API key for %s in .env. Auto-switched default AI to: %s (Model: %s)",
            chosen_provider.upper(), chosen_provider.upper(), chosen_model
        )
        print(f"\n======================================================================", flush=True)
        print(f" [AI Auto-Detect] Ollama is offline or not installed.", flush=True)
        print(f" Auto-selected default AI: {chosen_provider.upper()} (Model: {chosen_model})", flush=True)
        print(f" using credentials found in your .env configuration.", flush=True)
        print(f"======================================================================\n", flush=True)
    else:
        logger.warning(
            "[AI Auto-Detect] Ollama is unavailable and no alternative API keys (GROK_API_KEY / GEMINI_API_KEY) "
            "found in .env. Please configure an API key in Dashboard -> AI Settings."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown events."""
    db.init_db()
    ollama_ready = _ensure_ollama_model(OLLAMA_MODEL)
    if ollama_ready:
        _ensure_ollama_model(OLLAMA_VISION_MODEL)
    else:
        # If Ollama is failing or not installed, auto-configure fallback from .env
        _auto_configure_fallback_ai()
    yield


app = FastAPI(title="UsisAIn Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # local-only POC; tighten before any real deployment
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stream.router)
app.include_router(analyze.router)
app.include_router(scans.router)
app.include_router(tts.router)
app.include_router(reference_docs.router)
app.include_router(errors.router)

# Serve the web app (client/web-app/) directly from the backend — one
# process, no separate static server needed. /app/ -> analyze page,
# /app/dashboard/ -> dashboard page.
web_app_dir = settings.project_root / "client" / "web-app"
if web_app_dir.exists():
    app.mount("/app", StaticFiles(directory=str(web_app_dir), html=True), name="web-app")


@app.get("/")
def root():
    return {"status": "ok", "web_app": "/app", "endpoints": ["/api/analyze", "/api/analyze/stream", "/api/scans"]}


@app.get("/api/debug/env")
def debug_env():
    return {
        "sys_executable": sys.executable,
        "sys_path": sys.path,
        "venv_env": os.environ.get("VIRTUAL_ENV"),
    }


def get_local_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'


def _persist_env_var(key: str, val: str) -> None:
    """Update os.environ immediately and persist the key-value pair to .env."""
    clean_val = val.strip()
    os.environ[key] = clean_val
    env_path = settings.project_root / ".env"
    try:
        if env_path.exists():
            lines = env_path.read_text(encoding="utf-8").splitlines()
        else:
            lines = []
        found = False
        prefix = f"{key}="
        for i, line in enumerate(lines):
            if line.strip().startswith(prefix):
                lines[i] = f"{key}={clean_val}"
                found = True
                break
        if not found:
            lines.append(f"{key}={clean_val}")
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception as e:
        logger.warning("Failed to persist %s to .env: %s", key, e)


@app.get("/api/settings")
def get_settings():
    """Always re-read .env so the dashboard reflects the latest config."""
    from dotenv import load_dotenv
    from mcp_server.shared.ocr_utils import is_ocr_available
    from mcp_server.services.llm.key_pool import mask_key

    load_dotenv(settings.project_root / ".env", override=True)
    gem_key = os.environ.get("GEMINI_API_KEY", "")
    grok_key = os.environ.get("GROK_API_KEY", "")

    return {
        "default_llm_provider": os.environ.get("DEFAULT_LLM_PROVIDER", "ollama"),
        "default_language": os.environ.get("DEFAULT_LANGUAGE", "english"),
        "gemini_model": os.environ.get("GEMINI_MODEL", "gemini-3.5-flash"),
        "grok_model": os.environ.get("GROK_MODEL", "gpt-oss-120b"),
        "ollama_model": os.environ.get("OLLAMA_MODEL", "llama3.2:1b"),
        "ollama_vision_model": os.environ.get("OLLAMA_VISION_MODEL", "moondream"),
        "pipeline_step_timeout_seconds": float(os.environ.get("PIPELINE_STEP_TIMEOUT_SECONDS", "120.0")),
        "tts_enabled": os.environ.get("TTS_ENABLED", "False").lower() in ("true", "1", "yes"),
        "max_reference_doc_size_mb": float(os.environ.get("MAX_REFERENCE_DOC_SIZE_MB", "10.0")),
        "ocr_available": is_ocr_available(),
        "gemini_key_configured": bool(gem_key.strip()),
        "grok_key_configured": bool(grok_key.strip()),
        "gemini_key_masked": mask_key(gem_key),
        "grok_key_masked": mask_key(grok_key),
        "supported_languages": {
            "ollama": ["english"],
            "gemini": ["english", "taglish", "tagalog", "cebuano", "bisaya", "ilocano"],
            "grok": ["english", "taglish", "tagalog", "cebuano", "bisaya", "ilocano"],
        },
        "server_ip": get_local_ip(),
    }


@app.get("/api/settings/ai")
def get_ai_settings():
    """Detailed runtime configuration of all AI providers, keys, and models."""
    from dotenv import load_dotenv
    from mcp_server.shared.ocr_utils import is_ocr_available
    from mcp_server.services.llm.key_pool import mask_key

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


class UpdateAISettingsRequest(BaseModel):
    default_provider: str | None = None
    gemini_api_key: str | None = None
    gemini_model: str | None = None
    grok_api_key: str | None = None
    grok_model: str | None = None
    ollama_model: str | None = None
    ollama_vision_model: str | None = None


@app.post("/api/settings/ai")
def update_ai_settings(req: UpdateAISettingsRequest):
    """Update API keys, active models, or default provider in runtime and persist to .env."""
    if req.default_provider is not None:
        p = req.default_provider.strip().lower()
        if p in ("ollama", "gemini", "grok"):
            _persist_env_var("DEFAULT_LLM_PROVIDER", p)

    if req.gemini_api_key is not None:
        _persist_env_var("GEMINI_API_KEY", req.gemini_api_key)

    if req.gemini_model is not None and req.gemini_model.strip():
        _persist_env_var("GEMINI_MODEL", req.gemini_model)

    if req.grok_api_key is not None:
        _persist_env_var("GROK_API_KEY", req.grok_api_key)

    if req.grok_model is not None and req.grok_model.strip():
        _persist_env_var("GROK_MODEL", req.grok_model)

    if req.ollama_model is not None and req.ollama_model.strip():
        _persist_env_var("OLLAMA_MODEL", req.ollama_model)

    if req.ollama_vision_model is not None and req.ollama_vision_model.strip():
        _persist_env_var("OLLAMA_VISION_MODEL", req.ollama_vision_model)

    return {"status": "ok", "settings": get_ai_settings()}


class TestKeyRequest(BaseModel):
    provider: str
    api_key: str | None = None


@app.post("/api/settings/test-key")
async def test_api_key(req: TestKeyRequest):
    """Test Gemini or Grok key at runtime."""
    provider = req.provider.strip().lower()
    key = (req.api_key or "").strip()

    if provider == "gemini":
        from mcp_server.services.llm.gemini_client import GeminiProvider
        test_key = key or os.environ.get("GEMINI_API_KEY", "").split(",")[0].strip()
        if not test_key:
            return {"status": "error", "message": "No Gemini API key provided"}
        try:
            p = GeminiProvider(api_key=test_key)
            reply = await p.complete(system="You are a test ping.", user="Reply with the single word: OK", max_tokens=10)
            return {"status": "ok", "message": f"Connection successful! Model response: {reply}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    elif provider == "grok":
        from mcp_server.services.llm.grok_client import GrokProvider
        test_key = key or os.environ.get("GROK_API_KEY", "").split(",")[0].strip()
        if not test_key:
            return {"status": "error", "message": "No Grok API key provided"}
        try:
            p = GrokProvider(api_key=test_key)
            reply = await p.complete(system="You are a test ping.", user="Reply with the single word: OK", max_tokens=10)
            return {"status": "ok", "message": f"Connection successful! Model response: {reply}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    return {"status": "error", "message": f"Unknown provider: {provider}"}


class SwitchModelRequest(BaseModel):
    model: str


@app.get("/api/ollama/models")
def list_ollama_models():
    """List all locally available Ollama models with their sizes and modification dates."""
    active_model = os.environ.get("OLLAMA_MODEL", "llama3.2:1b").strip()
    active_vision = os.environ.get("OLLAMA_VISION_MODEL", "moondream").strip()
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").strip()

    try:
        import ollama as _ollama
    except ImportError:
        return {"models": [], "active_model": active_model, "active_vision_model": active_vision, "error": "ollama package not installed"}

    try:
        client = _ollama.Client(host=host)
        raw = client.list()
    except Exception as e:
        return {"models": [], "active_model": active_model, "active_vision_model": active_vision, "error": f"Cannot reach Ollama: {e}"}

    models_out = []
    items = []
    if hasattr(raw, "models"):
        items = raw.models
    elif isinstance(raw, dict) and "models" in raw:
        items = raw["models"]
    elif isinstance(raw, list):
        items = raw

    for m in items:
        name = getattr(m, "model", None) or (m.get("model") if isinstance(m, dict) else str(m))
        size = getattr(m, "size", None) or (m.get("size", 0) if isinstance(m, dict) else 0)
        modified_at = getattr(m, "modified_at", None) or (m.get("modified_at") if isinstance(m, dict) else None)
        
        if modified_at and not isinstance(modified_at, str):
            try:
                modified_at = modified_at.isoformat()
            except Exception:
                modified_at = str(modified_at)

        models_out.append({
            "name": str(name).strip(),
            "size_bytes": int(size or 0),
            "modified_at": str(modified_at or "")
        })

    return {"models": models_out, "active_model": active_model, "active_vision_model": active_vision}


@app.post("/api/ollama/switch-model")
def switch_ollama_model(req: SwitchModelRequest):
    """Switch the active Ollama text model and persist to .env."""
    new_model = req.model.strip()
    _persist_env_var("OLLAMA_MODEL", new_model)
    return {"status": "ok", "active_model": new_model}


class SwitchProviderRequest(BaseModel):
    provider: str


@app.post("/api/settings/switch-provider")
def switch_provider(req: SwitchProviderRequest | None = None, provider: str | None = None):
    """Switch the default LLM provider and persist to .env."""
    chosen_provider = (req.provider if req and req.provider else provider or "").strip().lower()
    if chosen_provider not in ("ollama", "gemini", "grok"):
        return {"status": "error", "message": "Invalid provider. Supported: ollama, gemini, grok"}
    _persist_env_var("DEFAULT_LLM_PROVIDER", chosen_provider)
    return {"status": "ok", "active_provider": chosen_provider}


class SwitchGeminiRequest(BaseModel):
    model: str = ""


@app.post("/api/settings/switch-gemini-model")
def switch_gemini_model(req: SwitchGeminiRequest | None = None, model: str | None = None):
    """Switch the active Gemini model and persist to .env."""
    chosen_model = (req.model if req and req.model else model or "").strip()
    if not chosen_model:
        return {"status": "error", "message": "Missing model parameter"}
    _persist_env_var("GEMINI_MODEL", chosen_model)
    return {"status": "ok", "gemini_model": chosen_model}


class SwitchGrokRequest(BaseModel):
    model: str = ""


@app.post("/api/settings/switch-grok-model")
def switch_grok_model(req: SwitchGrokRequest | None = None, model: str | None = None):
    """Switch the active Grok model and persist to .env."""
    chosen_model = (req.model if req and req.model else model or "").strip()
    if not chosen_model:
        return {"status": "error", "message": "Missing model parameter"}
    _persist_env_var("GROK_MODEL", chosen_model)
    return {"status": "ok", "grok_model": chosen_model}


@app.get("/api/grok/models")
def list_grok_models():
    """List Grok models either dynamically from xAI API if key exists, or defaults."""
    default_models = [
        {"name": "gpt-oss-120b", "description": "High-capacity reasoning & open-weight architecture (Recommended)"},
        {"name": "grok-4.1-fast", "description": "High-speed, cost-efficient reasoning & chat"},
        {"name": "grok-4.7", "description": "Flagship high-capability model"},
        {"name": "grok-4.6", "description": "Advanced reasoning model"},
        {"name": "grok-4.5", "description": "High-performance general model"},
        {"name": "grok-4.3", "description": "Long-context reasoning"},
        {"name": "grok-4.20-reasoning", "description": "Specialized deep reasoning model"},
        {"name": "grok-beta", "description": "Public beta preview"},
        {"name": "grok-2-vision-1212", "description": "Dedicated multimodal vision model"},
    ]
    from mcp_server.services.llm.grok_client import list_models, KEY_POOL, current_model
    if KEY_POOL.has_keys():
        try:
            live = list_models()
            models_out = [{"name": m, "description": "xAI Model"} for m in live]
            return {"models": models_out, "active_model": current_model()}
        except Exception:
            pass
    return {"models": default_models, "active_model": current_model()}


if __name__ == "__main__":
    import uvicorn
    local_ip = get_local_ip()
    print(f"Starting server on local IP: {local_ip}")
    uvicorn.run("usisain_backend.main:app", host="0.0.0.0", port=8000, reload=True, app_dir="src")



