



const GTTS_VOICES = [
  { name: "Google TTS - English (United States) (en-US)", lang: "en-US" },
  { name: "Google TTS - English (Great Britain) (en-GB)", lang: "en-GB" },
  { name: "Google TTS - English (Canada) (en-CA)", lang: "en-CA" },
  { name: "Google TTS - English (Australia) (en-AU)", lang: "en-AU" },
  { name: "Google TTS - English (India) (en-IN)", lang: "en-IN" },
  { name: "Google TTS - Filipino/Tagalog (tl-PH)", lang: "tl-PH" }
];

class TTSPlayer {
  constructor() {
    this.enabled = false;
    this.currentLanguage = "english";
    this.voices = GTTS_VOICES;
    this.selectedVoiceName = "Google TTS - English (United States) (en-US)";

    
    this._queue = [];
    this._isPlaying = false;
    this._currentAudio = null;
    this._aborted = false;
  }

  setEnabled(val) {
    this.enabled = !!val;
    if (!this.enabled) {
      this.stop();
    }
  }

  setLanguage(lang) {
    this.currentLanguage = lang || "english";
  }

  getLocaleCode(lang) {
    const map = {
      "english": "en-US",
      "taglish": "tl-PH",
      "tagalog": "tl-PH",
      "cebuano": "fil-PH",
      "bisaya": "fil-PH",
      "ilocano": "fil-PH"
    };
    return map[lang.toLowerCase()] || "en-US";
  }

  getVoices() {
    return this.voices;
  }

  setSelectedVoice(voiceName) {
    this.selectedVoiceName = voiceName;
  }

  initVoices() {
    this.voices = GTTS_VOICES;
  }

  _getBackendBase() {
    if (typeof window !== "undefined" && window.location.origin && window.location.origin.startsWith("http")) {
      return "";
    }
    return "";
  }

  speak(text) {
    if (!this.enabled || !text) return;

    
    this._queue.push({
      text,
      lang: this.currentLanguage,
      voice: this.selectedVoiceName
    });

    
    if (!this._isPlaying) {
      this._processQueue();
    }
  }

  async _processQueue() {
    if (this._isPlaying) return;
    this._isPlaying = true;
    this._aborted = false;

    while (this._queue.length > 0 && !this._aborted) {
      const item = this._queue.shift();
      try {
        await this._playItem(item);
      } catch (err) {
        console.error("TTS playback error:", err);
      }
    }

    this._isPlaying = false;
  }

  async _playItem(item) {
    const base = this._getBackendBase();
    const url = `${base}/api/tts/generate?text=${encodeURIComponent(item.text)}&language=${encodeURIComponent(item.lang)}&voice=${encodeURIComponent(item.voice || "")}`;

    const response = await fetch(url, { method: "POST" });
    if (!response.ok) {
      console.warn("Backend TTS generate returned non-ok status:", response.status);
      return;
    }

    const blob = await response.blob();
    const audioUrl = URL.createObjectURL(blob);

    return new Promise((resolve) => {
      const audio = new Audio(audioUrl);
      this._currentAudio = audio;

      audio.onended = () => {
        URL.revokeObjectURL(audioUrl);
        this._currentAudio = null;
        resolve();
      };

      audio.onerror = (err) => {
        console.error("Audio playback error:", err);
        URL.revokeObjectURL(audioUrl);
        this._currentAudio = null;
        resolve();
      };

      if (this._aborted) {
        URL.revokeObjectURL(audioUrl);
        this._currentAudio = null;
        resolve();
        return;
      }

      audio.play().catch(err => {
        console.warn("Audio play() rejected (autoplay policy):", err);
        URL.revokeObjectURL(audioUrl);
        this._currentAudio = null;
        resolve();
      });
    });
  }

  stop() {
    this._aborted = true;
    this._queue = [];

    if (this._currentAudio) {
      try {
        this._currentAudio.pause();
        this._currentAudio.currentTime = 0;
        if (this._currentAudio.src) {
          URL.revokeObjectURL(this._currentAudio.src);
        }
      } catch (e) {
        
      }
      this._currentAudio = null;
    }

    this._isPlaying = false;

    
    const base = this._getBackendBase();
    fetch(`${base}/api/tts/stop`, { method: "POST" }).catch(() => {});
  }
}


window.ttsPlayer = new TTSPlayer();
