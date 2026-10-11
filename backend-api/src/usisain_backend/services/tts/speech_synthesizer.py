import io
import re
import tempfile
import uuid
import wave
from pathlib import Path

from gtts import gTTS

from usisain_backend.services.tts.tts_player import tts_player


def synthesize(text: str, language: str = "english", voice: str | None = None) -> str:
    if voice:
        tts_player.selected_voice_name = voice
    tts_player.set_language(language)
    tts_player.speak(text)
    temp_dir = Path(tempfile.gettempdir())
    out_path = temp_dir / f"silence_{uuid.uuid4().hex}.wav"
    try:
        with wave.open(str(out_path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(1)
            w.setframerate(8000)
            w.writeframes(b"\x80" * 100)
    except Exception as e:
        print(f"Failed to generate dummy WAV: {e}")
    return str(out_path)


def generate_audio(text: str, language: str = "english", voice: str | None = None) -> io.BytesIO:
    clean_text = tts_player.sanitize(text)
    if not clean_text:
        buf = io.BytesIO(b"\xff\xfb\x90\x00" + b"\x00" * 413)
        buf.seek(0)
        return buf
    tagalog_pattern = re.compile(
        "\\b(ang|mga|ng|sa|na|ni|ay|si|po|opo|ako|ikaw|siya|ito|iyon|doon|dito|namin|nila|kaya|kasi|pero|maging|dahil|ano|sino|bakit|paano)\\b",
        re.IGNORECASE,
    )
    detected_lang = language
    if tagalog_pattern.search(clean_text):
        detected_lang = "tagalog"
    locale = tts_player.get_locale_code(detected_lang)
    if voice:
        tts_player.selected_voice_name = voice
    gtts_config = tts_player.get_gtts_config(locale)
    tts = gTTS(text=clean_text, lang=gtts_config["lang"], tld=gtts_config["tld"])
    buf = io.BytesIO()
    tts.write_to_fp(buf)
    buf.seek(0)
    return buf


def stop_playback():
    tts_player.stop()
