const BACKEND = "http://localhost:8000";


const LANGUAGE_MAP = {
  ollama: [
    { value: "english", label: "English" },
    { value: "taglish", label: "Taglish" },
    { value: "tagalog", label: "Tagalog" },
    { value: "cebuano", label: "Cebuano" },
    { value: "bisaya", label: "Bisaya" },
    { value: "ilocano", label: "Ilocano" },
  ],
  gemini: [
    { value: "english", label: "English" },
    { value: "taglish", label: "Taglish" },
    { value: "tagalog", label: "Tagalog" },
    { value: "cebuano", label: "Cebuano" },
    { value: "bisaya", label: "Bisaya" },
    { value: "ilocano", label: "Ilocano" },
  ],
  grok: [
    { value: "english", label: "English" },
    { value: "taglish", label: "Taglish" },
    { value: "tagalog", label: "Tagalog" },
    { value: "cebuano", label: "Cebuano" },
    { value: "bisaya", label: "Bisaya" },
    { value: "ilocano", label: "Ilocano" },
  ],
};


const languageSelect = document.getElementById("language-select");
const providerBadge = document.getElementById("provider-badge");
const providerName = document.getElementById("provider-name");
const btnAnalyze = document.getElementById("btn-analyze");
const btnDashboard = document.getElementById("btn-dashboard");
const statusEl = document.getElementById("status");
const historyList = document.getElementById("history");


btnAnalyze.addEventListener("click", () => {
  if (typeof chrome !== "undefined" && chrome.tabs) {
    chrome.tabs.create({ url: `${BACKEND}/app/` });
  } else {
    window.open(`${BACKEND}/app/`, "_blank");
  }
});

btnDashboard.addEventListener("click", () => {
  if (typeof chrome !== "undefined" && chrome.tabs) {
    chrome.tabs.create({ url: `${BACKEND}/app/dashboard/` });
  } else {
    window.open(`${BACKEND}/app/dashboard/`, "_blank");
  }
});

const ocrToggle = document.getElementById("ocr-toggle");
const ttsToggle = document.getElementById("tts-toggle");
const ttsVoiceRow = document.getElementById("tts-voice-row");
const ttsVoiceSelect = document.getElementById("tts-voice-select");


const GTTS_VOICES = [
  { name: "Google TTS - English (United States) (en-US)", lang: "en-US" },
  { name: "Google TTS - English (Great Britain) (en-GB)", lang: "en-GB" },
  { name: "Google TTS - English (Canada) (en-CA)", lang: "en-CA" },
  { name: "Google TTS - English (Australia) (en-AU)", lang: "en-AU" },
  { name: "Google TTS - English (India) (en-IN)", lang: "en-IN" },
  { name: "Google TTS - Filipino/Tagalog (tl-PH)", lang: "tl-PH" }
];


function populateVoiceDropdown() {
  if (!ttsVoiceSelect) return;
  ttsVoiceSelect.innerHTML = "";
  for (const voice of GTTS_VOICES) {
    const opt = document.createElement("option");
    opt.value = voice.name;
    opt.textContent = voice.name;
    ttsVoiceSelect.appendChild(opt);
  }
  
  if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
    chrome.storage.local.get(["selectedVoice"], (data) => {
      if (data.selectedVoice && ttsVoiceSelect.querySelector(`option[value="${CSS.escape(data.selectedVoice)}"]`)) {
        ttsVoiceSelect.value = data.selectedVoice;
      } else {
        ttsVoiceSelect.value = "Google TTS - English (United States) (en-US)";
      }
    });
  }
}

function updateTtsVoiceVisibility() {
  if (ttsVoiceRow) {
    ttsVoiceRow.style.display = ttsToggle.checked ? "flex" : "none";
  }
}

populateVoiceDropdown();


if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
  chrome.storage.local.get(["preferredLanguage", "useOcr", "useTts"], (data) => {
    if (data.preferredLanguage) {
      languageSelect.value = data.preferredLanguage;
    }
    if (data.useOcr !== undefined) {
      ocrToggle.checked = data.useOcr;
    }
    if (data.useTts !== undefined) {
      ttsToggle.checked = data.useTts;
    }
    updateTtsVoiceVisibility();
  });
}

if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
  chrome.storage.onChanged.addListener((changes) => {
    if (changes.useTts !== undefined) {
      ttsToggle.checked = !!changes.useTts.newValue;
      updateTtsVoiceVisibility();
    }
    if (changes.selectedVoice !== undefined) {
      if (ttsVoiceSelect && changes.selectedVoice.newValue && ttsVoiceSelect.querySelector(`option[value="${CSS.escape(changes.selectedVoice.newValue)}"]`)) {
        ttsVoiceSelect.value = changes.selectedVoice.newValue;
      }
    }
  });
}


languageSelect.addEventListener("change", () => {
  if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
    chrome.storage.local.set({ preferredLanguage: languageSelect.value });
  }
});


ocrToggle.addEventListener("change", () => {
  if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
    chrome.storage.local.set({ useOcr: ocrToggle.checked });
  }
});


ttsToggle.addEventListener("change", () => {
  if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
    chrome.storage.local.set({ useTts: ttsToggle.checked });
  }
  updateTtsVoiceVisibility();
});


if (ttsVoiceSelect) {
  ttsVoiceSelect.addEventListener("change", () => {
    if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
      chrome.storage.local.set({ selectedVoice: ttsVoiceSelect.value });
    }
  });
}


function populateLanguages(provider) {
  const languages = LANGUAGE_MAP[provider] || LANGUAGE_MAP.gemini;
  chrome.storage.local.get(["preferredLanguage"], (data) => {
    const saved = data?.preferredLanguage || languageSelect.value || "english";
    languageSelect.innerHTML = "";
    for (const lang of languages) {
      const option = document.createElement("option");
      option.value = lang.value;
      option.textContent = lang.label;
      languageSelect.appendChild(option);
    }

    const validValues = languages.map((l) => l.value);
    if (validValues.includes(saved)) {
      languageSelect.value = saved;
    } else {
      languageSelect.value = "english";
    }
  });
}


let activeProvider = "ollama";
let activeOllamaModel = "";
let activeGeminiModel = "";
let activeGrokModel = "gpt-oss-120b";
let allOllamaModels = [];
const allGeminiModels = [
  { name: "gemini-3.5-flash", size_bytes: null, modified_at: null },
  { name: "gemini-2.5-flash", size_bytes: null, modified_at: null },
  { name: "gemini-2.5-pro", size_bytes: null, modified_at: null },
  { name: "gemini-2.0-flash", size_bytes: null, modified_at: null },
  { name: "gemini-2.0-pro-exp-02-05", size_bytes: null, modified_at: null },
  { name: "gemini-1.5-flash", size_bytes: null, modified_at: null },
  { name: "gemini-1.5-pro", size_bytes: null, modified_at: null }
];
let allGrokModels = [
  { name: "gpt-oss-120b", size_bytes: null, modified_at: null },
  { name: "grok-4.1-fast", size_bytes: null, modified_at: null },
  { name: "grok-4.7", size_bytes: null, modified_at: null },
  { name: "grok-4.6", size_bytes: null, modified_at: null },
  { name: "grok-4.5", size_bytes: null, modified_at: null },
  { name: "grok-4.3", size_bytes: null, modified_at: null },
  { name: "grok-4.20-reasoning", size_bytes: null, modified_at: null },
  { name: "grok-beta", size_bytes: null, modified_at: null },
  { name: "grok-2-vision-1212", size_bytes: null, modified_at: null }
];

async function loadSettings() {
  try {
    const res = await fetch(`${BACKEND}/api/settings`);
    const settings = await res.json();
    
    if (settings?.server_ip) {
      const serverIpVal = document.getElementById("server-ip-value");
      if (serverIpVal) {
        serverIpVal.textContent = `${settings.server_ip}:8000`;
      }
    }
    
    if (settings?.default_llm_provider) {
      activeProvider = settings.default_llm_provider;
    }
    const geminiM = settings?.gemini_model || settings?.models?.gemini;
    if (geminiM) {
      activeGeminiModel = geminiM;
    }
    const grokM = settings?.grok_model || settings?.models?.grok;
    if (grokM) {
      activeGrokModel = grokM;
    }
    const ollamaM = settings?.ollama_model || settings?.models?.ollama;
    if (ollamaM) {
      activeOllamaModel = ollamaM;
    }

    const ocrAvailable = !!settings?.ocr_available;
    const ocrBadge = document.getElementById("ocr-status-badge");
    if (ocrBadge) {
      if (ocrAvailable) {
        ocrBadge.textContent = "Installed ✓";
        ocrBadge.className = "ocr-status-badge ocr-available";
        ocrBadge.title = "Tesseract-OCR is installed and active on the system.";
      } else {
        ocrBadge.textContent = "Not Installed";
        ocrBadge.className = "ocr-status-badge ocr-missing";
        ocrBadge.title = "Tesseract-OCR is not installed on this system. OCR extraction unavailable.";
      }
    }
    if (ocrToggle && !ocrAvailable) {
      ocrToggle.checked = false;
      ocrToggle.disabled = true;
      ocrToggle.title = "Tesseract-OCR is not installed on this system.";
    }

    if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
      chrome.storage.local.set({
        activeProvider,
        activeGeminiModel,
        activeGrokModel,
        activeOllamaModel,
        ocrAvailable
      });
    }

    if (window.updateLlmSelectorUI) {
      window.updateLlmSelectorUI();
    }
    if (window.updateActiveModelUI) {
      window.updateActiveModelUI();
    }

    const provider = activeProvider.toLowerCase();

    
    if (settings.supported_languages && settings.supported_languages[provider]) {
      const serverLangs = settings.supported_languages[provider];
      LANGUAGE_MAP[provider] = serverLangs.map((v) => ({
        value: v,
        label: v.charAt(0).toUpperCase() + v.slice(1),
      }));
    }

    populateLanguages(provider);
  } catch (err) {
    console.error("Failed to load settings:", err);
    populateLanguages("gemini");
  }
}


function getVerdictClass(verdict) {
  if (!verdict) return "unknown";
  const v = verdict.toLowerCase();
  if (v.includes("fake") || v.includes("scam") || v.includes("mislead") || v.includes("false") || v.includes("dangerous"))
    return "dangerous";
  if (v.includes("suspicious") || v.includes("questionable") || v.includes("unverified") || v.includes("partially"))
    return "suspicious";
  if (v.includes("real") || v.includes("true") || v.includes("authentic") || v.includes("legitimate") || v.includes("safe"))
    return "safe";
  return "unknown";
}


async function loadHistory() {
  try {
    const scans = await fetch(`${BACKEND}/api/scans?limit=15`).then((r) => r.json());

    if (scans.length) {
      statusEl.textContent = "Recent scans";
      statusEl.className = "connected";
    } else {
      statusEl.textContent = "No scans yet — right-click text or an image to start.";
      statusEl.className = "";
    }

    historyList.innerHTML = "";

    if (!scans.length) {
      historyList.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">🔍</div>
          <div class="empty-title">No scans yet</div>
          <div class="empty-desc">Right-click on text, images, or videos to analyze them for scams and misinformation.</div>
        </div>`;
      return;
    }

    for (let i = 0; i < scans.length; i++) {
      const s = scans[i];
      const li = document.createElement("li");
      li.style.animationDelay = `${i * 0.05}s`;

      const verdict = s.step3_verdict ?? "—";
      const verdictClass = getVerdictClass(verdict);
      const summary = (s.input_summary || "").slice(0, 80);

      li.innerHTML = `
        <div class="top-row">
          <span class="channel-tag">${s.channel}</span>
          <span class="verdict-tag ${verdictClass}">${verdict}</span>
        </div>
        <div class="summary-text">${summary}</div>`;
      historyList.appendChild(li);
    }
  } catch {
    statusEl.textContent = "Can't reach backend — is it running on localhost:8000?";
    statusEl.className = "error";
  }
}


(async () => {
  await loadSettings();
  loadHistory();
  await initModelSelector();
})();


async function initModelSelector() {
  const container = document.getElementById("ollama-selector-container");
  const trigger = document.getElementById("model-trigger");
  const dropdown = document.getElementById("model-dropdown");
  const searchInput = document.getElementById("model-search");
  const listContainer = document.getElementById("model-list");
  const activeNameSpan = document.getElementById("active-model-name");
  const overlay = document.getElementById("model-switch-overlay");
  const statusIndicator = container?.querySelector(".model-status-indicator");

  const llmContainer = document.getElementById("llm-selector-container");
  const llmTrigger = document.getElementById("llm-trigger");
  const llmDropdown = document.getElementById("llm-dropdown");
  const llmList = document.getElementById("llm-list");
  const activeLlmName = document.getElementById("active-llm-name");

  if (!trigger || !dropdown || !searchInput || !listContainer) return;

  
  trigger.addEventListener("click", (e) => {
    e.stopPropagation();
    const isOpen = trigger.classList.toggle("open");
    dropdown.classList.toggle("visible");
    trigger.setAttribute("aria-expanded", isOpen);
    if (isOpen) {
      searchInput.focus();
      searchInput.value = "";
      renderModelList("");
      if (llmTrigger) {
        llmTrigger.classList.remove("open");
        llmDropdown.classList.remove("visible");
        llmTrigger.setAttribute("aria-expanded", "false");
      }
    }
  });

  
  document.addEventListener("click", (e) => {
    if (!container.contains(e.target)) {
      trigger.classList.remove("open");
      dropdown.classList.remove("visible");
      trigger.setAttribute("aria-expanded", "false");
    }
  });

  
  searchInput.addEventListener("input", (e) => {
    renderModelList(e.target.value);
  });

  
  searchInput.addEventListener("click", (e) => {
    e.stopPropagation();
  });

  
  if (llmTrigger && llmDropdown && llmList) {
    llmTrigger.addEventListener("click", (e) => {
      e.stopPropagation();
      const isOpen = llmTrigger.classList.toggle("open");
      llmDropdown.classList.toggle("visible");
      llmTrigger.setAttribute("aria-expanded", isOpen);
      
      trigger.classList.remove("open");
      dropdown.classList.remove("visible");
      trigger.setAttribute("aria-expanded", "false");
    });

    document.addEventListener("click", (e) => {
      if (llmContainer && !llmContainer.contains(e.target)) {
        llmTrigger.classList.remove("open");
        llmDropdown.classList.remove("visible");
        llmTrigger.setAttribute("aria-expanded", "false");
      }
    });

    
    const llmItems = llmList.querySelectorAll(".model-item");
    llmItems.forEach(item => {
      item.addEventListener("click", async (e) => {
        e.stopPropagation();
        const newProvider = item.getAttribute("data-value");
        
        llmTrigger.classList.remove("open");
        llmDropdown.classList.remove("visible");
        llmTrigger.setAttribute("aria-expanded", "false");

        if (newProvider === activeProvider) return;

        if (overlay) {
          overlay.querySelector(".loading-text").textContent = `Switching to ${newProvider.toUpperCase()}...`;
          overlay.classList.add("show");
        }

        try {
          const res = await fetch(`${BACKEND}/api/settings/switch-provider`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ provider: newProvider })
          }).then(r => r.json());

          if (res && res.status === "ok") {
            activeProvider = newProvider;
            updateLlmSelectorUI();
            await loadSettings();
            await fetchAndRenderModels();
          }
        } catch (err) {
          console.error("Error switching provider:", err);
        } finally {
          if (overlay) overlay.classList.remove("show");
        }
      });
    });
  }

  function updateLlmSelectorUI() {
    if (activeLlmName) {
      if (activeProvider === "ollama") {
        activeLlmName.textContent = "Ollama (Local)";
      } else if (activeProvider === "gemini") {
        activeLlmName.textContent = "Gemini (Cloud)";
      } else if (activeProvider === "grok") {
        activeLlmName.textContent = "Grok (xAI)";
      } else {
        activeLlmName.textContent = activeProvider.toUpperCase();
      }
    }
    const llmItems = llmList?.querySelectorAll(".model-item");
    if (llmItems) {
      llmItems.forEach(item => {
        const val = item.getAttribute("data-value");
        const badge = item.querySelector(".model-item-status-badge");
        const check = item.querySelector(".model-item-check");
        if (val === activeProvider) {
          item.classList.add("active-model");
          if (check) check.style.display = "";
          if (badge) {
            badge.className = "model-item-status-badge status-active";
            badge.textContent = "Active";
          }
        } else {
          item.classList.remove("active-model");
          if (check) check.style.display = "none";
          if (badge) {
            badge.className = "model-item-status-badge status-available";
            badge.textContent = val === "ollama" ? "Local Host" : "Cloud API";
          }
        }
      });
    }
    const badge = document.querySelector(".llm-provider-badge");
    if (badge) {
      if (activeProvider === "ollama") {
        badge.style.backgroundColor = "var(--accent-indigo)";
        badge.style.boxShadow = "0 0 8px var(--accent-indigo)";
      } else if (activeProvider === "gemini") {
        badge.style.backgroundColor = "var(--verdict-safe)";
        badge.style.boxShadow = "0 0 8px var(--verdict-safe)";
      } else if (activeProvider === "grok") {
        badge.style.backgroundColor = "#10b981";
        badge.style.boxShadow = "0 0 8px rgba(16, 185, 129, 0.4)";
      }
    }
  }

  window.updateLlmSelectorUI = updateLlmSelectorUI;
  updateLlmSelectorUI();

  await fetchAndRenderModels();

  function isVisionModel(name, provider) {
    if (!name) return false;
    const p = (provider || activeProvider || "").toLowerCase();
    if (p === "gemini") return true;
    const lower = name.toLowerCase();
    const visionKeywords = ["vision", "moondream", "llava", "bakllava", "minicpm-v", "scout", "multimodal", "-vl", "vl-", "_vl"];
    return visionKeywords.some(kw => lower.includes(kw));
  }

  async function fetchAndRenderModels() {
    updateActiveModelUI();

    if (activeProvider === "ollama") {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 2500);
        const data = await fetch(`${BACKEND}/api/ollama/models`, { signal: controller.signal })
          .then(r => r.json())
          .finally(() => clearTimeout(timeoutId));
        
        if (trigger) trigger.disabled = false;
        allOllamaModels = data.models || [];
        if (data.active_model) activeOllamaModel = data.active_model;
        if (data.active_vision_model) activeVisionModel = data.active_vision_model;

        if (statusIndicator) {
          statusIndicator.style.backgroundColor = data.error ? "var(--verdict-dangerous)" : "var(--verdict-safe)";
          statusIndicator.style.boxShadow = data.error ? "0 0 8px var(--verdict-dangerous)" : "0 0 8px var(--verdict-safe)";
        }
      } catch (err) {
        if (trigger) trigger.disabled = false;
        if (statusIndicator) {
          statusIndicator.style.backgroundColor = "var(--verdict-dangerous)";
          statusIndicator.style.boxShadow = "0 0 8px var(--verdict-dangerous)";
        }
      }
    } else if (activeProvider === "gemini") {
      if (trigger) trigger.disabled = false;
      try {
        const geminiData = await fetch(`${BACKEND}/api/gemini/models`).then(r => r.json());
        if (geminiData?.models && geminiData.models.length > 0) {
          allGeminiModels = geminiData.models;
        }
        if (geminiData?.active_model) {
          activeGeminiModel = geminiData.active_model;
        }
      } catch (err) {
        console.warn("Using default gemini models in popup:", err);
      }
      if (statusIndicator) {
        statusIndicator.style.backgroundColor = "var(--verdict-safe)";
        statusIndicator.style.boxShadow = "0 0 8px var(--verdict-safe)";
      }
    } else if (activeProvider === "grok") {
      if (trigger) trigger.disabled = false;
      try {
        const grokData = await fetch(`${BACKEND}/api/grok/models`).then(r => r.json());
        if (grokData?.models && grokData.models.length > 0) {
          allGrokModels = grokData.models;
        }
        if (grokData?.active_model) {
          activeGrokModel = grokData.active_model;
        }
      } catch (err) {
        console.warn("Using default grok models in popup:", err);
      }
      if (statusIndicator) {
        statusIndicator.style.backgroundColor = "var(--verdict-safe)";
        statusIndicator.style.boxShadow = "0 0 8px var(--verdict-safe)";
      }
    }
    updateActiveModelUI();
  }

  function updateActiveModelUI() {
    if (!activeNameSpan) return;
    
    let currentActive = "";
    if (activeProvider === "ollama") {
      currentActive = activeOllamaModel;
    } else if (activeProvider === "gemini") {
      currentActive = activeGeminiModel;
    } else if (activeProvider === "grok") {
      currentActive = activeGrokModel;
    }

    const triggerBadge = document.getElementById("active-model-badge");
    if (currentActive) {
      const sVis = isVisionModel(currentActive, activeProvider);
      activeNameSpan.textContent = cleanModelName(currentActive);
      activeNameSpan.title = `${cleanModelName(currentActive)} (${sVis ? '👁️ Vision + Text' : '📝 Text Only'})`;
      if (triggerBadge) {
        triggerBadge.textContent = sVis ? "👁️ Vision" : "📝 Text";
        triggerBadge.className = `trigger-mode-badge ${sVis ? 'mode-vision' : 'mode-text'}`;
        triggerBadge.title = sVis ? "Supports Text + Images" : "Text Only (No images)";
      }
    } else {
      activeNameSpan.textContent = "Select Model";
      if (triggerBadge) {
        triggerBadge.textContent = "";
        triggerBadge.className = "trigger-mode-badge";
      }
    }
    renderModelList("");
  }

  window.updateActiveModelUI = updateActiveModelUI;
  window.fetchAndRenderModels = fetchAndRenderModels;

  function cleanModelName(rawName) {
    if (!rawName) return "Unknown";
    let name = rawName;
    
    if (name.startsWith("gemini-")) {
      if (name.includes("3.5-flash")) return "Gemini 3.5 Flash";
      if (name.includes("2.5-flash")) return "Gemini 2.5 Flash";
      if (name.includes("2.5-pro")) return "Gemini 2.5 Pro";
      if (name.includes("2.0-flash")) return "Gemini 2.0 Flash";
      if (name.includes("2.0-pro")) return "Gemini 2.0 Pro";
      if (name.includes("1.5-flash")) return "Gemini 1.5 Flash";
      if (name.includes("1.5-pro")) return "Gemini 1.5 Pro";
      return name;
    }

    if (name === "gpt-oss-120b" || name === "openai/gpt-oss-120b") return "GPT OSS 120B";
    if (name === "gpt-oss-20b" || name === "openai/gpt-oss-20b") return "GPT OSS 20B";
    if (name === "qwen/qwen3.8-27b") return "Qwen 3.8 27B";
    if (name === "allam-2-7b") return "Allam 2 7B";

    if (name.startsWith("grok-")) {
      if (name === "grok-4.1-fast") return "Grok 4.1 Fast";
      if (name === "grok-4.7") return "Grok 4.7";
      if (name === "grok-4.6") return "Grok 4.6";
      if (name === "grok-4.5") return "Grok 4.5";
      if (name === "grok-4.3") return "Grok 4.3";
      if (name === "grok-4.20-reasoning") return "Grok 4.20 Reasoning";
      if (name === "grok-beta") return "Grok Beta";
      if (name === "grok-2-vision-1212") return "Grok 2 Vision";
      return name.replace(/^grok-/, "Grok ").replace(/-/g, " ");
    }

    if (name.includes(":")) {
      name = name.split(":")[0];
    }
    name = name.replace(/[-_]/g, " ");
    
    const lower = name.toLowerCase();
    if (lower.includes("llama3.2")) return "Llama 3.2";
    if (lower.includes("llama3.1")) return "Llama 3.1";
    if (lower.includes("llama3")) return "Llama 3";
    if (lower.includes("deepseek")) return "DeepSeek R1";
    if (lower.includes("qwen")) return "Qwen 2.5";
    if (lower.includes("gemma")) return "Gemma 3";
    if (lower.includes("moondream")) return "Moondream 2";
    
    return name.split(" ").map(word => {
      if (word.length === 0) return "";
      return word.charAt(0).toUpperCase() + word.slice(1);
    }).join(" ");
  }

  function formatSize(bytes) {
    if (!bytes || bytes === 0) return "0.0 GB";
    const gb = bytes / (1024 * 1024 * 1024);
    return `${gb.toFixed(1)} GB`;
  }

  function formatRelativeTime(isoString) {
    if (!isoString) return "";
    try {
      const date = new Date(isoString);
      if (isNaN(date.getTime())) return "";
      const now = new Date();
      const diffMs = now - date;
      const diffMins = Math.round(diffMs / 60000);
      if (diffMins < 1) return "Just now";
      if (diffMins < 60) return `${diffMins}m ago`;
      return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    } catch (e) {
      return "";
    }
  }

  function renderModelList(query) {
    listContainer.innerHTML = "";
    const filter = query.toLowerCase().trim();
    
    const modelsToRender = activeProvider === "ollama" 
      ? allOllamaModels 
      : (activeProvider === "gemini" ? allGeminiModels : allGrokModels);
    const filtered = modelsToRender.filter(m => {
      const sVis = (typeof m.supports_vision === "boolean") ? m.supports_vision : isVisionModel(m.name, activeProvider);
      const capKeywords = sVis ? "vision image multimodal text" : "text only";
      return m.name.toLowerCase().includes(filter) || capKeywords.includes(filter);
    });

    if (filtered.length === 0) {
      if (modelsToRender.length === 0) {
        if (activeProvider === "ollama") {
          renderEmptyState("No local Ollama models found.");
        } else if (activeProvider === "gemini") {
          renderEmptyState("No Gemini models configured.");
        } else {
          renderEmptyState("No Grok models configured.");
        }
      } else {
        renderEmptyState("No matching models found.");
      }
      return;
    }

    filtered.forEach(model => {
      const activeModelName = activeProvider === "ollama" 
        ? activeOllamaModel 
        : (activeProvider === "gemini" ? activeGeminiModel : activeGrokModel);
      const isTxtActive = model.name === activeModelName || model.name.split(":")[0] === activeModelName.split(":")[0];
      const isActive = isTxtActive;
      const supportsVision = (typeof model.supports_vision === "boolean")
        ? model.supports_vision
        : isVisionModel(model.name, activeProvider);

      const item = document.createElement("div");
      item.className = `model-item ${isActive ? 'active-model' : ''}`;
      
      const relativeTime = formatRelativeTime(model.modified_at);

      item.innerHTML = `
        <div class="model-item-info">
          <div class="model-item-header">
            <span class="model-item-name" title="${model.name}">${cleanModelName(model.name)}</span>
            <span class="model-mode-badge ${supportsVision ? 'mode-vision' : 'mode-text'}">
              ${supportsVision ? '👁️ Image+Text' : '📝 Text Only'}
            </span>
            <span class="model-item-status-badge ${isActive ? 'status-active' : 'status-available'}">
              ${isActive ? 'Active' : 'Available'}
            </span>
          </div>
          <div class="model-item-details">
            ${model.size_bytes ? `<span class="model-item-size">${formatSize(model.size_bytes)}</span>` : '<span class="model-item-size">API Cloud</span>'}
            <span class="model-item-divider">•</span>
            <span class="model-capability-badge ${supportsVision ? 'cap-vision' : 'cap-text'}" title="${supportsVision ? 'Supports multimodal visual inspection & text' : 'Pure text model'}">
              ${supportsVision ? '👁️ Vision + Text' : '📝 Text Only'}
            </span>
            ${relativeTime ? `<span class="model-item-divider">•</span> <span class="model-item-modified">${relativeTime}</span>` : ''}
          </div>
        </div>
        ${isActive ? '<span class="model-item-check">✓</span>' : ''}
      `;

      item.addEventListener("click", async (e) => {
        e.stopPropagation();
        if (isActive) {
          trigger.classList.remove("open");
          dropdown.classList.remove("visible");
          trigger.setAttribute("aria-expanded", "false");
          return;
        }

        if (overlay) {
          overlay.querySelector(".loading-text").textContent = `Switching to ${cleanModelName(model.name)}...`;
          overlay.classList.add("show");
        }

        try {
          let res;
          if (activeProvider === "ollama") {
            res = await fetch(`${BACKEND}/api/ollama/switch-model`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ model: model.name })
            }).then(r => r.json());
          } else if (activeProvider === "gemini") {
            res = await fetch(`${BACKEND}/api/settings/switch-gemini-model`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ model: model.name })
            }).then(r => r.json());
          } else if (activeProvider === "grok") {
            res = await fetch(`${BACKEND}/api/settings/switch-grok-model`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ model: model.name })
            }).then(r => r.json());
          }
          
          trigger.classList.remove("open");
          dropdown.classList.remove("visible");
          trigger.setAttribute("aria-expanded", "false");

          if (res && res.status === "ok") {
            if (activeProvider === "ollama") {
              activeOllamaModel = model.name;
            } else if (activeProvider === "gemini") {
              activeGeminiModel = model.name;
            } else if (activeProvider === "grok") {
              activeGrokModel = model.name;
            }
            await loadSettings();
          }
        } catch (err) {
          console.error("Error switching model:", err);
        } finally {
          if (overlay) overlay.classList.remove("show");
          updateActiveModelUI();
        }
      });

      listContainer.appendChild(item);
    });
  }

  function renderEmptyState(message) {
    listContainer.innerHTML = `
      <div class="model-selector-empty">
        <div class="empty-icon">🧠</div>
        <div>${message}</div>
      </div>
    `;
  }
}
