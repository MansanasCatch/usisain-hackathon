"""main.py — entrypoint. Run with:
    uvicorn usisain_backend.main:app --reload --app-dir src --port 8000
(from inside backend-api/, with the venv active)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.logging import setup_logging
from .data import db
from .api import stream, analyze, scans, tts

setup_logging()
db.init_db()

app = FastAPI(title="UsisAIn Backend")

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


@app.get("/")
def root():
    return {"status": "ok", "endpoints": ["/api/analyze", "/api/analyze/stream", "/api/scans"]}
