import io
import os
import re
import tempfile
from gtts import gTTS
import pygame
from playsound import playsound

class TTSPlayer:
    def __init__(self):
        self.enabled = True
        self.current_language = "english"
        self.selected_voice_name = ""

    def set_enabled(self, val: bool):
        self.enabled = bool(val)
        if not self.enabled:
            self.stop()

    def set_language(self, lang: str):
        self.current_language = lang or "english"

    def get_locale_code(self, lang: str) -> str:
        lang_map = {
            "english": "en-US",
            "taglish": "tl-PH",
            "tagalog": "tl-PH",
            "cebuano": "fil-PH",
            "bisaya": "fil-PH",
            "ilocano": "fil-PH"
        }
        return lang_map.get(lang.lower(), "en-US")

    def sanitize(self, text: str) -> str:
        if not text:
            return ""

        # 1. Remove dangerous script, style, and iframe blocks along with their inner code contents (XSS/Audio poisoning mitigation)
        sanitized = re.sub(r'<script\b[^<]*(?:(?!</script>)<[^<]*)*</script>', '', text, flags=re.I | re.S)
        sanitized = re.sub(r'<style\b[^<]*(?:(?!</style>)<[^<]*)*</style>', '', sanitized, flags=re.I | re.S)
        sanitized = re.sub(r'<iframe\b[^<]*(?:(?!</iframe>)<[^<]*)*</iframe>', '', sanitized, flags=re.I | re.S)

        # 2. Strip remaining HTML tags
        sanitized = re.sub(r'<[^>]*>', '', sanitized)

        # 3. Remove raw javascript commands and coding operators/brackets
        sanitized = re.sub(r'(?:console\.log|alert\s*\(|eval\s*\(|prompt\s*\(|confirm\s*\(|window\.|document\.)', '', sanitized, flags=re.I)
        sanitized = re.sub(r'[\{\}\[\]\(\)\<\>\=\+\-\*\/\\`_]', ' ', sanitized)
        sanitized = re.sub(r'\s+', ' ', sanitized)
        sanitized = sanitized.strip()

        # 4. Clean markdown formatting
        sanitized = re.sub(r'\[([^\]]+)\]\((https?://[^\s)]+)\)', r'\1', sanitized)
        sanitized = re.sub(r'\*\*([^*]+)\*\*', r'\1', sanitized)

        return sanitized.strip()

    def get_gtts_config(self, lang_code: str) -> dict:
        # Default fallback is en-US equivalent in gTTS: lang='en', tld='com'
        config = {"lang": "en", "tld": "com"}

        # Clean up key for lookup
        key = lang_code.strip().lower()

        # Mapping voice selection names and standard locales
        voice_map = {
            # Microsoft native voices
            "microsoft david - english (united states) (en-us)": {"lang": "en", "tld": "com"},
            "microsoft zira - english (united states) (en-us)": {"lang": "en", "tld": "com"},
            "microsoft hazel - english (great britain) (en-gb)": {"lang": "en", "tld": "co.uk"},
            "microsoft heera - english (india) (en-in)": {"lang": "en", "tld": "co.in"},
            "microsoft mark - english (united states) (en-us)": {"lang": "en", "tld": "com"},
            # Standard locale codes
            "en-us": {"lang": "en", "tld": "com"},
            "en-gb": {"lang": "en", "tld": "co.uk"},
            "en-ca": {"lang": "en", "tld": "ca"},
            "en-au": {"lang": "en", "tld": "com.au"},
            "en-in": {"lang": "en", "tld": "co.in"},
            "en-ie": {"lang": "en", "tld": "ie"},
            "en-za": {"lang": "en", "tld": "co.za"},
            "en-ng": {"lang": "en", "tld": "com.ng"},
            "tl-ph": {"lang": "tl", "tld": "com"},
            "fil-ph": {"lang": "tl", "tld": "com"},
            "tl": {"lang": "tl", "tld": "com"},
        }

        # Direct match check in voice_map
        if key in voice_map:
            return voice_map[key]

        # Check if the currently configured selected_voice_name matches
        voice_name_lower = self.selected_voice_name.strip().lower() if self.selected_voice_name else ""
        if voice_name_lower in voice_map:
            return voice_map[voice_name_lower]

        # Fallbacks using substring matches
        if "en-us" in key or "united states" in key:
            return {"lang": "en", "tld": "com"}
        elif "en-gb" in key or "great britain" in key:
            return {"lang": "en", "tld": "co.uk"}
        elif "en-in" in key or "india" in key:
            return {"lang": "en", "tld": "co.in"}
        elif "en-au" in key or "australia" in key:
            return {"lang": "en", "tld": "com.au"}
        elif "tl" in key or "fil" in key or "tagalog" in key or "filipino" in key:
            return {"lang": "tl", "tld": "com"}

        return config

    def speak(self, text: str):
        if not self.enabled or not text:
            return

        clean_text = self.sanitize(text)
        if not clean_text:
            return

        # Detect if the text contains Tagalog keywords to dynamically adjust voice pronunciation
        text_language = self.current_language
        tagalog_pattern = re.compile(
            r'\b(ang|mga|ng|sa|na|ni|ay|si|po|opo|ako|ikaw|siya|ito|iyon|doon|dito|namin|nila|kaya|kasi|pero|maging|dahil|ano|sino|bakit|paano)\b',
            re.IGNORECASE
        )
        if tagalog_pattern.search(clean_text):
            text_language = "tagalog"

        # Split text into shorter clauses to avoid speech synth buffer truncation or hangs
        sentences = re.split(r'[.!?；。]+', clean_text)
        for sentence in sentences:
            trimmed = sentence.strip()
            if trimmed:
                self.play_sentence(trimmed, text_language)

    def play_sentence(self, sentence_text: str, lang: str):
        locale = self.get_locale_code(lang)
        gtts_config = self.get_gtts_config(locale)

        # Generate speech using gTTS
        tts = gTTS(text=sentence_text, lang=gtts_config["lang"], tld=gtts_config["tld"])

        # Try in-memory playing first using pygame/io (leaving no files behind at all)
        try:
            fp = io.BytesIO()
            tts.write_to_fp(fp)
            fp.seek(0)

            # Initialize pygame mixer
            if not pygame.mixer.get_init():
                pygame.mixer.init()

            pygame.mixer.music.load(fp, 'mp3')
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            pygame.mixer.music.unload()
            return
        except Exception as e:
            # Fallback to saving to a temp file and playing it with playsound
            try:
                # Save to a temporary file in OS temp directory (not in the project folder)
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
                    tts.write_to_fp(temp_file)
                    temp_path = temp_file.name

                try:
                    playsound(temp_path)
                finally:
                    # Attempt to remove the temporary file immediately
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass
            except Exception as fallback_err:
                print(f"TTS Playback failed with both pygame and playsound fallback: {e} | {fallback_err}")

    def stop(self):
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
        except Exception:
            pass

# Create a singleton-like instance for import
tts_player = TTSPlayer()
