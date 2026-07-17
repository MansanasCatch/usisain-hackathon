"""
speech_synthesizer.py — local TTS on the final aggregated explanation.
Uses Google Text-to-Speech (gTTS) for high-quality audio synthesis and
plays it locally through speakers using pygame/playsound.
"""

import uuid
import tempfile
import wave
from pathlib import Path
from .tts_player import tts_player

def synthesize(text: str, language: str = "english", voice: str = None) -> str:
    """Plays the speech audio immediately through speakers and returns a temporary silence WAV path."""
    # Set the current player configurations
    if voice:
        tts_player.selected_voice_name = voice
    tts_player.set_language(language)

    # Automatically play the speech immediately through the computer's speakers
    tts_player.speak(text)

    # Generate a small 100-sample dummy silent WAV file in OS temp folder for FastAPI FileResponse compatibility
    temp_dir = Path(tempfile.gettempdir())
    out_path = temp_dir / f"silence_{uuid.uuid4().hex}.wav"

    try:
        with wave.open(str(out_path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(1)
            w.setframerate(8000)
            w.writeframes(b'\x80' * 100)  # 100 samples of silence (128/0x80 is silence in 8-bit unsigned PCM)
    except Exception as e:
        print(f"Failed to generate dummy WAV: {e}")

    return str(out_path)

def stop_playback():
    """Stops any currently active audio playback."""
    tts_player.stop()
