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

from .core.logging import setup_logging
from .core.config import settings
from .data import db
from .api import stream, analyze, scans, tts, reference_docs, errors

setup_logging()
logger = logging.getLogger(__name__)

OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:1b")
OLLAMA_VISION_MODEL = os.environ.get("OLLAMA_VISION_MODEL", "moondream")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")


def _ensure_ollama_model(model_name: str):
    """Check that Ollama is reachable and the given model is pulled.
    Auto-pulls the model if it's missing — blocks startup briefly but means
    the user never has to run `ollama pull` manually."""
    # Ensure variables are stripped of whitespace/carriage returns
    model_name = model_name.strip()
    host_name = OLLAMA_HOST.strip()

    try:
        import ollama
    except ImportError:
        logger.warning("ollama package not installed — skipping model check")
        return

    client = ollama.Client(host=host_name)

    # 1. Check connectivity
    try:
        models = client.list()
    except Exception as e:
        logger.error(
            "[Ollama] Cannot reach Ollama at %s -- is it running? "
            "Start it with `ollama serve` in another terminal. Error: %s",
            host_name, e,
        )
        return

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

    logger.info("Ollama check - model: %r", model_name)
    logger.info("Ollama check - available models: %r", available)

    model_present = False
    for name in available:
        # Clean both names
        name_clean = name.strip()
        if model_name == name_clean or model_name.split(":")[0] == name_clean.split(":")[0]:
            model_present = True
            break

    if model_present:
        logger.info("[Ollama] Model '%s' is ready", model_name)
        return

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
                # Print progress every 10% to keep logs clean
                if pct % 10 == 0 and pct != last_logged_pct:
                    last_logged_pct = pct
                    logger.info("[Ollama] Pull progress for '%s': %d%% completed", model_name, pct)
                    
        logger.info("[Ollama] Successfully pulled '%s'", model_name)
    except Exception as e:
        logger.error("[Ollama] Failed to pull model '%s': %s", model_name, e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown events."""
    db.init_db()
    _ensure_ollama_model(OLLAMA_MODEL)
    _ensure_ollama_model(OLLAMA_VISION_MODEL)
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


@app.get("/api/settings")
def get_settings():
    """Always re-read .env so the dashboard reflects the latest config."""
    from dotenv import load_dotenv
    load_dotenv(settings.project_root / ".env", override=True)
    return {
        "default_llm_provider": os.environ.get("DEFAULT_LLM_PROVIDER", "ollama"),
        "default_language": os.environ.get("DEFAULT_LANGUAGE", "english"),
        "gemini_model": os.environ.get("GEMINI_MODEL", "gemini-3.5-flash"),
        "ollama_model": os.environ.get("OLLAMA_MODEL", "llama3.2:1b"),
        "ollama_vision_model": os.environ.get("OLLAMA_VISION_MODEL", "moondream"),
        "pipeline_step_timeout_seconds": float(os.environ.get("PIPELINE_STEP_TIMEOUT_SECONDS", "120.0")),
        "tts_enabled": os.environ.get("TTS_ENABLED", "False").lower() in ("true", "1", "yes"),
        "max_reference_doc_size_mb": float(os.environ.get("MAX_REFERENCE_DOC_SIZE_MB", "10.0")),
        "supported_languages": {
            "ollama": ["english"],
            "gemini": ["english", "taglish", "tagalog", "cebuano", "bisaya", "ilocano"],
        },
    }


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
        
        # Format modified_at if it's a datetime object
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
    os.environ["OLLAMA_MODEL"] = new_model

    # Persist to .env file
    env_path = settings.project_root / ".env"
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
        found = False
        for i, line in enumerate(lines):
            if line.strip().startswith("OLLAMA_MODEL="):
                lines[i] = f"OLLAMA_MODEL={new_model}"
                found = True
                break
        if not found:
            lines.append(f"OLLAMA_MODEL={new_model}")
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception as e:
        logger.warning("Failed to persist OLLAMA_MODEL to .env: %s", e)

    return {"status": "ok", "active_model": new_model}

