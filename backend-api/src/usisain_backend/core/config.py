"""config.py — centralized settings. Every value has a sensible default
except the API keys, which must come from .env (see README for where to
get each one)."""

import os
from pathlib import Path
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[3]  # backend/
PROJECT_ROOT = BACKEND_DIR.parent
load_dotenv(PROJECT_ROOT / ".env", override=True)


class Settings:
    # Paths
    project_root: Path = PROJECT_ROOT
    data_dir: Path = PROJECT_ROOT / "data"
    uploads_dir: Path = PROJECT_ROOT / "data" / "uploads"
    reference_images_dir: Path = PROJECT_ROOT / "data" / "reference_images"
    db_path: Path = PROJECT_ROOT / "data" / "app.db"
    mcp_server_path: Path = PROJECT_ROOT / "mcp_server" / "server.py"

    # LLM
    default_llm_provider: str = os.environ.get("DEFAULT_LLM_PROVIDER", "ollama")
    default_language: str = os.environ.get("DEFAULT_LANGUAGE", "english")
    gemini_model: str = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
    ollama_model: str = os.environ.get("OLLAMA_MODEL", "llama3.2:1b")
    ollama_vision_model: str = os.environ.get("OLLAMA_VISION_MODEL", "moondream")

    # Text-to-speech
    tts_enabled: bool = os.environ.get("TTS_ENABLED", "False").lower() in ("true", "1", "yes")

    # Messenger bot (only needed if you run client/messenger_bot/)
    meta_verify_token: str | None = os.environ.get("META_VERIFY_TOKEN")
    meta_page_access_token: str | None = os.environ.get("META_PAGE_ACCESS_TOKEN")
    meta_app_secret: str | None = os.environ.get("META_APP_SECRET")

    # Pipeline timeout (seconds)
    pipeline_step_timeout_seconds: float = float(os.environ.get("PIPELINE_STEP_TIMEOUT_SECONDS", "120.0"))

    # Step 3 settings
    step3_fast_query_gen: bool = os.environ.get("STEP3_FAST_QUERY_GEN", "True").lower() in ("true", "1", "yes")
    step3_fetch_full_page: bool = os.environ.get("STEP3_FETCH_FULL_PAGE", "False").lower() in ("true", "1", "yes")

    # Video analysis
    max_video_frames: int = int(os.environ.get("MAX_VIDEO_FRAMES", "24"))

    # Upload restrictions (reference documents)
    max_reference_doc_size_mb: float = float(os.environ.get("MAX_REFERENCE_DOC_SIZE_MB", "10.0"))


settings = Settings()
settings.uploads_dir.mkdir(parents=True, exist_ok=True)
settings.reference_images_dir.mkdir(parents=True, exist_ok=True)
