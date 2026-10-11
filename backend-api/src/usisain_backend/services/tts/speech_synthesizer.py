"""
speech_synthesizer.py — local TTS on the final aggregated explanation.
Uses Google Text-to-Speech (gTTS) for high-quality audio synthesis.
Supports two modes:
  1. Server-speaker playback (pygame) for local-machine usage
  2. Audio byte generation for browser-side playback (mobile/remote)
"""

import io
import re
import uuid
import tempfile
import wave
from pathlib import Path
from gtts import gTTS

from usisain_backend.services.tts.tts_player import tts_player

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


def generate_audio(text: str, language: str = "english", voice: str = None) -> io.BytesIO:
    """Generate TTS audio as MP3 bytes for browser-side playback (mobile/remote devices).
    Does NOT play through the server speakers — returns raw audio data."""
    clean_text = tts_player.sanitize(text)
    if not clean_text:
        # Return a tiny silent MP3 frame
        buf = io.BytesIO(b'\xff\xfb\x90\x00' + b'\x00' * 413)
        buf.seek(0)
        return buf

    # Detect Tagalog keywords
    tagalog_pattern = re.compile(
        r'\b(ang|mga|ng|sa|na|ni|ay|si|po|opo|ako|ikaw|siya|ito|iyon|doon|dito|namin|nila|kaya|kasi|pero|maging|dahil|ano|sino|bakit|paano)\b',
        re.IGNORECASE
    )
    detected_lang = language
    if tagalog_pattern.search(clean_text):
        detected_lang = "tagalog"

    locale = tts_player.get_locale_code(detected_lang)

    # Apply voice override if provided
    if voice:
        tts_player.selected_voice_name = voice

    gtts_config = tts_player.get_gtts_config(locale)

    tts = gTTS(text=clean_text, lang=gtts_config["lang"], tld=gtts_config["tld"])
    buf = io.BytesIO()
    tts.write_to_fp(buf)
    buf.seek(0)
    return buf


def stop_playback():
    """Stops any currently active audio playback."""
    tts_player.stop()
