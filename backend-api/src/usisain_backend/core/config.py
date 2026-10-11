import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[3]
PROJECT_ROOT = BACKEND_DIR.parent
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE), env_file_encoding="utf-8", extra="ignore"
    )
    project_root: Path = PROJECT_ROOT
    data_dir: Path = PROJECT_ROOT / "data"
    uploads_dir: Path = PROJECT_ROOT / "data" / "uploads"
    reference_images_dir: Path = PROJECT_ROOT / "data" / "reference_images"
    db_path: Path = PROJECT_ROOT / "data" / "app.db"
    mcp_server_path: Path = PROJECT_ROOT / "mcp_server" / "server.py"
    default_llm_provider: str = "ollama"
    default_language: str = "english"
    gemini_model: str = "gemini-3.5-flash"
    ollama_model: str = "llama3.2:1b"
    ollama_vision_model: str = "moondream"
    ollama_host: str = "http://localhost:11434"
    grok_model: str = "gpt-oss-120b"
    gemini_api_key: str = ""
    grok_api_key: str = ""
    gemini_rpm_limit: int = 15
    tts_enabled: bool = False
    pipeline_step_timeout_seconds: float = 120.0
    step3_fast_query_gen: bool = True
    step3_fetch_full_page: bool = False
    max_video_frames: int = 24
    max_reference_doc_size_mb: float = 10.0

    def persist_env_var(self, key: str, val: str) -> None:
        clean_val = val.strip()
        os.environ[key] = clean_val
        try:
            if ENV_FILE.exists():
                lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
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
            ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except Exception:
            pass


settings = Settings()
settings.uploads_dir.mkdir(parents=True, exist_ok=True)
settings.reference_images_dir.mkdir(parents=True, exist_ok=True)
