from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from ..services.tts.speech_synthesizer import synthesize, stop_playback, generate_audio
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


@router.post("/generate")
def generate_speech(text: str, language: str = "english", voice: str = None):
    """Generate TTS audio and return it as an MP3 stream for browser playback.
    This endpoint does NOT play through the server speakers — the browser plays it."""
    if not settings.tts_enabled:
        raise HTTPException(
            status_code=400,
            detail="Text-to-speech is disabled in configuration settings."
        )
    audio_bytes = generate_audio(text, language, voice)
    return StreamingResponse(
        audio_bytes,
        media_type="audio/mpeg",
        headers={"Content-Disposition": "inline; filename=speech.mp3"}
    )


@router.post("/stop")
def stop_speech():
    stop_playback()
    return JSONResponse(content={"status": "ok", "message": "Playback stopped"})
