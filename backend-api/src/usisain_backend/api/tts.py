from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import FileResponse

from ..services.tts.speech_synthesizer import synthesize

router = APIRouter(prefix="/api/tts", tags=["tts"])


@router.post("")
def text_to_speech(text: str, language: str = "english"):
    path = synthesize(text, language)
    return FileResponse(path, media_type="audio/wav", filename=Path(path).name)
