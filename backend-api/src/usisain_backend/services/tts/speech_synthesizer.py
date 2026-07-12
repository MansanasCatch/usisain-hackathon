"""
speech_synthesizer.py — local TTS on the final aggregated explanation.
Runs once, on the combined output, not per-step (see architecture notes).

Uses pyttsx3, which wraps the OS's built-in voices (SAPI5 on Windows) —
fully offline, no API key. English quality is reliably good since every
Windows install ships English voices. Tagalog quality depends entirely on
whether a Filipino voice pack is installed on the machine (Windows
Settings → Time & Language → Speech → Add voices) — if none is installed,
this falls back to whatever default voice is present, which will
mispronounce Tagalog text. There's no good fully-offline Tagalog TTS
option as of this writing; if quality matters more than staying fully
local, swap this module for a cloud TTS API (e.g. Google Cloud
Text-to-Speech) without changing callers.
"""

import uuid
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parents[5] / "data" / "tts_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def synthesize(text: str, language: str = "english") -> str:
    """Returns the path to a generated .wav file."""
    import pyttsx3

    engine = pyttsx3.init()
    voices = engine.getProperty("voices")

    if language in ("taglish", "tagalog", "cebuano", "ilocano"):
        # Best-effort: look for any installed voice whose name/id hints at
        # Filipino/Tagalog. Falls back to the default voice if none found.
        for voice in voices:
            if any(hint in (voice.name or "").lower() for hint in ("filipino", "tagalog", "ph")):
                engine.setProperty("voice", voice.id)
                break

    out_path = OUTPUT_DIR / f"{uuid.uuid4().hex}.wav"
    engine.save_to_file(text, str(out_path))
    engine.runAndWait()
    return str(out_path)
