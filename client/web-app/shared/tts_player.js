// tts_player.js — Modular Client-Side Text-to-Speech via Backend Python gTTS.
// Bypasses browser speechSynthesis to play high-quality gTTS audio via backend speakers.

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

  speak(text) {
    if (!this.enabled || !text) return;

    // Send the speech request to the backend API
    const backendUrl = typeof window !== "undefined" && window.location.origin.includes("localhost:8000")
      ? "/api/tts"
      : "http://localhost:8000/api/tts";

    const lang = this.currentLanguage || "english";
    const selectedVoice = this.selectedVoiceName || "";

    fetch(`${backendUrl}?text=${encodeURIComponent(text)}&language=${encodeURIComponent(lang)}&voice=${encodeURIComponent(selectedVoice)}`, {
      method: "POST"
    })
    .then(response => {
      if (!response.ok) {
        console.warn("Backend TTS returned non-ok status:", response.status);
      }
    })
    .catch(err => {
      console.error("Failed to play TTS via backend:", err);
    });
  }

  stop() {
    const backendUrl = typeof window !== "undefined" && window.location.origin.includes("localhost:8000")
      ? "/api/tts/stop"
      : "http://localhost:8000/api/tts/stop";

    fetch(backendUrl, { method: "POST" })
    .then(response => {
      if (!response.ok) {
        console.warn("Backend TTS stop returned non-ok status:", response.status);
      }
    })
    .catch(err => {
      console.error("Failed to stop backend TTS:", err);
    });
  }
}

// Export single instance for global usage
window.ttsPlayer = new TTSPlayer();
