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

    // 1. Remove dangerous script, style, and iframe blocks along with their inner code contents (XSS/Audio poisoning mitigation)
    let sanitized = text
      .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, "")
      .replace(/<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>/gi, "")
      .replace(/<iframe\b[^<]*(?:(?!<\/iframe>)<[^<]*)*<\/iframe>/gi, "");

    // 2. Strip remaining HTML tags
    sanitized = sanitized.replace(/<[^>]*>/g, "");

    // 3. Remove raw javascript commands and coding operators/brackets
    sanitized = sanitized
      .replace(/(?:console\.log|alert\s*\(|eval\s*\(|prompt\s*\(|confirm\s*\(|window\.|document\.)/gi, "")
      .replace(/[\{\}\[\]\(\)\<\>\=\+\-\*\/\\`_]/g, " ")
      .replace(/\s+/g, " ")
      .trim();

    // 4. Clean markdown formatting
    const cleanText = sanitized
      .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, "$1")
      .replace(/\*\*([^*]+)\*\*/g, "$1")
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
    if (locale === "tl-PH") {
      matchingVoice = this.voices.find(v => v.lang.toLowerCase().startsWith("tl") || v.lang.toLowerCase().includes("fil"));
    }
    if (!matchingVoice && this.selectedVoiceName) {
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
      if (e.error !== "interrupted" && e.error !== "canceled") {
        console.warn("TTS Playback error:", e);
      }
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
