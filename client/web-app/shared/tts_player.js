// tts_player.js — Modular Client-Side Text-to-Speech using Browser SpeechSynthesis.
// Fully free, local, offline, high-performance, and has zero impact on backend servers.

class TTSPlayer {
  constructor() {
    this.enabled = false;
    this.currentLanguage = "english";
    this.utteranceQueue = [];
    this.isSpeaking = false;
    this.voices = [];
    this.selectedVoiceName = "";

    // Retrieve initial voices list
    if (typeof window !== "undefined" && window.speechSynthesis) {
      this.voices = window.speechSynthesis.getVoices();
      window.speechSynthesis.onvoiceschanged = () => {
        this.voices = window.speechSynthesis.getVoices();
      };
    }
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
      "cebuano": "fil-PH", // Cebuano/Bisaya fall back to Filipino voice if native ceb is unavailable
      "bisaya": "fil-PH",
      "ilocano": "fil-PH"
    };
    return map[lang.toLowerCase()] || "en-US";
  }

  speak(text) {
    if (!this.enabled || !text) return;

    // Clean text: strip HTML, markdown formatting, and links for clean speech
    const cleanText = text
      .replace(/<[^>]*>/g, "") // remove HTML tags
      .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, "$1") // markdown links -> just text
      .replace(/\*\*([^*]+)\*\*/g, "$1") // bold
      .replace(/[\*\#\_]/g, "") // markdown characters
      .trim();

    if (!cleanText) return;

    // Detect if the text contains Tagalog keywords to dynamically adjust voice pronunciation
    let textLanguage = this.currentLanguage;
    const tagalogPattern = /\b(ang|mga|ng|sa|na|ni|ay|si|po|opo|ako|ikaw|siya|ito|iyon|doon|dito|namin|nila|kaya|kasi|pero|maging|dahil|ano|sino|bakit|paano)\b/i;
    if (tagalogPattern.test(cleanText)) {
      textLanguage = "tagalog";
    }

    // Split text into shorter clauses to avoid speech synth buffer truncation or hangs
    const sentences = cleanText.split(/[.!?；。]+/);
    for (const sentence of sentences) {
      const trimmed = sentence.trim();
      if (trimmed.length > 0) {
        this.enqueue(trimmed, textLanguage);
      }
    }
  }

  enqueue(text, lang) {
    this.utteranceQueue.push({ text, lang: lang || this.currentLanguage });
    this.processQueue();
  }

  processQueue() {
    if (this.isSpeaking || this.utteranceQueue.length === 0 || !window.speechSynthesis) return;

    this.isSpeaking = true;
    const item = this.utteranceQueue.shift();
    const utterance = new SpeechSynthesisUtterance(item.text);
    const locale = this.getLocaleCode(item.lang);
    utterance.lang = locale;

    // Locate the best matching voice
    let matchingVoice = null;
    if (this.selectedVoiceName) {
      matchingVoice = this.voices.find(v => v.name === this.selectedVoiceName);
    }
    if (!matchingVoice) {
      matchingVoice = this.voices.find(v => v.lang.startsWith(locale) || v.lang.includes(locale.split("-")[0]));
    }
    if (matchingVoice) {
      utterance.voice = matchingVoice;
    }

    utterance.onend = () => {
      this.isSpeaking = false;
      this.processQueue();
    };

    utterance.onerror = (e) => {
      console.warn("TTS Playback error:", e);
      this.isSpeaking = false;
      this.processQueue();
    };

    window.speechSynthesis.speak(utterance);
  }

  stop() {
    this.utteranceQueue = [];
    this.isSpeaking = false;
    if (typeof window !== "undefined" && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
  }
}

// Export single instance for global usage
window.ttsPlayer = new TTSPlayer();
