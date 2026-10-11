import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from usisain_backend.api import (
    analyze,
    errors,
    reference_docs,
    scans,
    stream,
    tts,
)
from usisain_backend.api import (
    settings as settings_router,
)
from usisain_backend.core.config import settings
from usisain_backend.data import db
from usisain_backend.services.bootstrap_service import (
    auto_configure_fallback_ai,
    ensure_ollama_model,
)
from usisain_backend.services.browser_launcher import schedule_browser_launch


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    ollama_ready = ensure_ollama_model(settings.ollama_model)
    if ollama_ready:
        ensure_ollama_model(settings.ollama_vision_model)
    else:
        auto_configure_fallback_ai()
    asyncio.create_task(schedule_browser_launch())
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="UsisAIn Backend", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
    )
    app.include_router(stream.router)
    app.include_router(analyze.router)
    app.include_router(scans.router)
    app.include_router(tts.router)
    app.include_router(reference_docs.router)
    app.include_router(errors.router)
    app.include_router(settings_router.router)
    web_app_dir = settings.project_root / "client" / "web-app"
    if web_app_dir.exists():
        app.mount("/app", StaticFiles(directory=str(web_app_dir), html=True), name="web-app")
    return app
