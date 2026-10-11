import io
import os
import queue
import re
import tempfile
import threading

import pygame
from gtts import gTTS


class TTSPlayer:
    def __init__(self):
        self.enabled = True
        self.current_language = "english"
        self.selected_voice_name = ""
        self.queue = queue.Queue()
        self._abort_current = False
        self._stop_event = threading.Event()
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

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
            "ilocano": "fil-PH",
        }
        return lang_map.get(lang.lower(), "en-US")

    def sanitize(self, text: str) -> str:
        if not text:
            return ""
        sanitized = re.sub(
            "<script\\b[^<]*(?:(?!</script>)<[^<]*)*</script>", "", text, flags=re.I | re.S
        )
        sanitized = re.sub(
            "<style\\b[^<]*(?:(?!</style>)<[^<]*)*</style>", "", sanitized, flags=re.I | re.S
        )
        sanitized = re.sub(
            "<iframe\\b[^<]*(?:(?!</iframe>)<[^<]*)*</iframe>", "", sanitized, flags=re.I | re.S
        )
        sanitized = re.sub("<[^>]*>", "", sanitized)
        sanitized = re.sub(
            "(?:console\\.log|alert\\s*\\(|eval\\s*\\(|prompt\\s*\\(|confirm\\s*\\(|window\\.|document\\.)",
            "",
            sanitized,
            flags=re.I,
        )
        sanitized = re.sub("[\\{\\}\\[\\]\\(\\)\\<\\>\\=\\+\\-\\*\\/\\\\`_]", " ", sanitized)
        sanitized = re.sub("\\s+", " ", sanitized)
        sanitized = sanitized.strip()
        sanitized = re.sub("\\[([^\\]]+)\\]\\((https?://[^\\s)]+)\\)", "\\1", sanitized)
        sanitized = re.sub("\\*\\*([^*]+)\\*\\*", "\\1", sanitized)
        return sanitized.strip()

    def get_gtts_config(self, lang_code: str) -> dict:
        config = {"lang": "en", "tld": "com"}
        key = lang_code.strip().lower()
        voice_map = {
            "microsoft david - english (united states) (en-us)": {"lang": "en", "tld": "com"},
            "microsoft zira - english (united states) (en-us)": {"lang": "en", "tld": "com"},
            "microsoft hazel - english (great britain) (en-gb)": {"lang": "en", "tld": "co.uk"},
            "microsoft heera - english (india) (en-in)": {"lang": "en", "tld": "co.in"},
            "microsoft mark - english (united states) (en-us)": {"lang": "en", "tld": "com"},
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
        if key in voice_map:
            return voice_map[key]
        voice_name_lower = (
            self.selected_voice_name.strip().lower() if self.selected_voice_name else ""
        )
        if voice_name_lower in voice_map:
            return voice_map[voice_name_lower]
        if "en-us" in key or "united states" in key:
            return {"lang": "en", "tld": "com"}
        elif "en-gb" in key or "great britain" in key:
            return {"lang": "en", "tld": "co.uk"}
        elif "en-in" in key or "india" in key:
            return {"lang": "en", "tld": "co.in"}
        elif "en-au" in key or "australia" in key:
            return {"lang": "en", "tld": "com.au"}
        elif "tl" in key or "fil" in key or "tagalog" in key or ("filipino" in key):
            return {"lang": "tl", "tld": "com"}
        return config

    def speak(self, text: str):
        if not self.enabled or not text:
            return
        self.queue.put(
            {"text": text, "lang": self.current_language, "voice": self.selected_voice_name}
        )

    def _worker_loop(self):
        while not self._stop_event.is_set():
            try:
                item = self.queue.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                self._abort_current = False
                self._play_item(item)
            except Exception as e:
                print(f"Error playing queued item: {e}")
            finally:
                self.queue.task_done()

    def _play_item(self, item: dict):
        text = item["text"]
        lang = item["lang"]
        voice = item["voice"]
        clean_text = self.sanitize(text)
        if not clean_text:
            return
        text_language = lang
        tagalog_pattern = re.compile(
            "\\b(ang|mga|ng|sa|na|ni|ay|si|po|opo|ako|ikaw|siya|ito|iyon|doon|dito|namin|nila|kaya|kasi|pero|maging|dahil|ano|sino|bakit|paano)\\b",
            re.IGNORECASE,
        )
        if tagalog_pattern.search(clean_text):
            text_language = "tagalog"
        sentences = re.split("[.!?；。]+", clean_text)
        for sentence in sentences:
            if self._abort_current:
                break
            trimmed = sentence.strip()
            if trimmed:
                self.play_sentence(trimmed, text_language, voice)

    def play_sentence(self, sentence_text: str, lang: str, voice: str):
        locale = self.get_locale_code(lang)
        gtts_config = self.get_gtts_config(locale)
        tts = gTTS(text=sentence_text, lang=gtts_config["lang"], tld=gtts_config["tld"])
        try:
            fp = io.BytesIO()
            tts.write_to_fp(fp)
            fp.seek(0)
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(fp, "mp3")
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy() and (not self._abort_current):
                pygame.time.Clock().tick(10)
            pygame.mixer.music.unload()
            return
        except Exception as e:
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
                    tts.write_to_fp(temp_file)
                    temp_path = temp_file.name
                try:
                    if not self._abort_current:
                        from playsound import playsound

                        playsound(temp_path)
                finally:
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass
            except Exception as fallback_err:
                print(
                    f"TTS Playback failed with both pygame and playsound fallback: {e} | {fallback_err}"
                )

    def stop(self):
        self._abort_current = True
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
                self.queue.task_done()
            except queue.Empty:
                break
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
        except Exception:
            pass


tts_player = TTSPlayer()
