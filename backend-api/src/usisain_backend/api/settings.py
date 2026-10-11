import os
import sys

from dotenv import load_dotenv
from fastapi import APIRouter

from mcp_server.shared.ocr_utils import is_ocr_available
from usisain_backend.api.schemas.settings import (
    SwitchGeminiRequest,
    SwitchGrokRequest,
    SwitchModelRequest,
    SwitchProviderRequest,
    TestKeyRequest,
    UpdateAISettingsRequest,
)
from usisain_backend.core.config import settings
from usisain_backend.services.settings_service import (
    get_ai_settings,
    get_local_ip,
    get_ollama_status,
    list_grok_models,
    list_ollama_models,
    start_pull_ollama_model,
    test_api_key,
    update_ai_settings,
)

router = APIRouter(tags=["settings"])


@router.get("/")
def root():
    return {
        "status": "ok",
        "web_app": "/app",
        "endpoints": ["/api/analyze", "/api/analyze/stream", "/api/scans"],
    }


@router.get("/api/debug/env")
def debug_env():
    return {
        "sys_executable": sys.executable,
        "sys_path": sys.path,
        "venv_env": os.environ.get("VIRTUAL_ENV"),
    }


@router.get("/api/settings")
def get_settings():
    load_dotenv(settings.project_root / ".env", override=True)
    cur_provider = os.environ.get("DEFAULT_LLM_PROVIDER", settings.default_llm_provider)
    cur_gemini = os.environ.get("GEMINI_MODEL", settings.gemini_model)
    cur_ollama = os.environ.get("OLLAMA_MODEL", settings.ollama_model)
    cur_ollama_v = os.environ.get("OLLAMA_VISION_MODEL", settings.ollama_vision_model)
    cur_grok = os.environ.get("GROK_MODEL", settings.grok_model)
    return {
        "default_llm_provider": cur_provider,
        "default_language": settings.default_language,
        "tts_enabled": settings.tts_enabled,
        "ocr_available": is_ocr_available(),
        "gemini_model": cur_gemini,
        "ollama_model": cur_ollama,
        "ollama_vision_model": cur_ollama_v,
        "grok_model": cur_grok,
        "models": {
            "gemini": cur_gemini,
            "ollama": cur_ollama,
            "ollama_vision": cur_ollama_v,
            "grok": cur_grok,
        },
        "server_ip": get_local_ip(),
        "supported_languages": {
            "ollama": ["english", "taglish", "tagalog", "cebuano", "bisaya", "ilocano"],
            "gemini": ["english", "taglish", "tagalog", "cebuano", "bisaya", "ilocano"],
            "grok": ["english", "taglish", "tagalog", "cebuano", "bisaya", "ilocano"],
        },
    }


@router.get("/api/settings/ai")
def read_ai_settings():
    return get_ai_settings()


@router.post("/api/settings/ai")
def modify_ai_settings(req: UpdateAISettingsRequest):
    return update_ai_settings(
        default_provider=req.default_provider,
        gemini_api_key=req.gemini_api_key,
        gemini_model=req.gemini_model,
        grok_api_key=req.grok_api_key,
        grok_model=req.grok_model,
        ollama_model=req.ollama_model,
        ollama_vision_model=req.ollama_vision_model,
    )


@router.post("/api/settings/test-key")
def check_test_key(req: TestKeyRequest):
    return test_api_key(provider=req.provider, api_key=req.api_key)


@router.get("/api/ollama/status")
def get_ollama_system_status():
    return get_ollama_status()


@router.post("/api/ollama/pull-model")
def trigger_pull_ollama_model(req: SwitchModelRequest | None = None):
    model = (req.model if req and req.model else "llama3.2:1b").strip()
    return start_pull_ollama_model(model)


@router.get("/api/ollama/models")
def get_ollama_models():
    return list_ollama_models()


@router.post("/api/ollama/switch-model")
def switch_ollama_model(req: SwitchModelRequest):
    new_model = req.model.strip()
    settings.persist_env_var("OLLAMA_MODEL", new_model)
    return {"status": "ok", "active_model": new_model}


@router.post("/api/settings/switch-provider")
def switch_provider(req: SwitchProviderRequest | None = None, provider: str | None = None):
    chosen = (req.provider if req and req.provider else provider or "").strip().lower()
    if chosen not in ("ollama", "gemini", "grok"):
        return {"status": "error", "message": "Invalid provider. Supported: ollama, gemini, grok"}
    settings.persist_env_var("DEFAULT_LLM_PROVIDER", chosen)
    return {"status": "ok", "active_provider": chosen}


@router.post("/api/settings/switch-gemini-model")
def switch_gemini_model(req: SwitchGeminiRequest):
    new_model = req.model.strip()
    if new_model:
        settings.persist_env_var("GEMINI_MODEL", new_model)
    return {"status": "ok", "active_model": os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")}


@router.post("/api/settings/switch-grok-model")
def switch_grok_model(req: SwitchGrokRequest):
    new_model = req.model.strip()
    if new_model:
        settings.persist_env_var("GROK_MODEL", new_model)
    return {"status": "ok", "active_model": os.environ.get("GROK_MODEL", "gpt-oss-120b")}


@router.get("/api/grok/models")
def get_grok_models():
    return list_grok_models()


@router.get("/api/gemini/models")
def get_gemini_models():
    ai = get_ai_settings()
    return {
        "models": [
            {
                "name": m,
                "description": "Google Gemini Cloud",
                "supports_vision": True,
                "capability": "Vision + Text",
            }
            for m in ai.get("gemini", {}).get("available_models", [])
        ],
        "active_model": os.environ.get("GEMINI_MODEL", "gemini-3.5-flash"),
    }
