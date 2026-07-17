from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from ..services.tts.speech_synthesizer import synthesize, stop_playback
from ..core.config import settings

router = APIRouter(prefix="/api/tts", tags=["tts"])


@router.post("")
def text_to_speech(text: str, language: str = "english", voice: str = None):
    if not settings.tts_enabled:
        raise HTTPException(
            status_code=400,
            detail="Text-to-speech is disabled in configuration settings."
        )
    path = synthesize(text, language, voice)
    return FileResponse(path, media_type="audio/wav", filename=Path(path).name)


@router.post("/stop")
def stop_speech():
    stop_playback()
    return JSONResponse(content={"status": "ok", "message": "Playback stopped"})
