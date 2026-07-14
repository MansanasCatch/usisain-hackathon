from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..services.tts.speech_synthesizer import synthesize
from ..core.config import settings

router = APIRouter(prefix="/api/tts", tags=["tts"])


@router.post("")
def text_to_speech(text: str, language: str = "english"):
    if not settings.tts_enabled:
        raise HTTPException(
            status_code=400,
            detail="Text-to-speech is disabled in configuration settings."
        )
    path = synthesize(text, language)
    return FileResponse(path, media_type="audio/wav", filename=Path(path).name)
