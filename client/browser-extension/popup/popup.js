const BACKEND = "http://localhost:8000";

// ─── All supported languages per provider ───
const LANGUAGE_MAP = {
  ollama: [
    { value: "english", label: "English" },
  ],
  gemini: [
    { value: "english", label: "English" },
    { value: "taglish", label: "Taglish" },
    { value: "tagalog", label: "Tagalog" },
    { value: "cebuano", label: "Cebuano" },
    { value: "bisaya", label: "Bisaya" },
    { value: "ilocano", label: "Ilocano" },
  ],
};

// ─── DOM references ───
const languageSelect = document.getElementById("language-select");
const providerBadge = document.getElementById("provider-badge");
const providerName = document.getElementById("provider-name");
const btnAnalyze = document.getElementById("btn-analyze");
const btnDashboard = document.getElementById("btn-dashboard");
const statusEl = document.getElementById("status");
const historyList = document.getElementById("history");

// ─── Navigation buttons ───
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

// ─── Voice dropdown population ───
const GTTS_VOICES = [
  { name: "Google TTS - English (United States) (en-US)", lang: "en-US" },
  { name: "Google TTS - English (Great Britain) (en-GB)", lang: "en-GB" },
  { name: "Google TTS - English (Canada) (en-CA)", lang: "en-CA" },
  { name: "Google TTS - English (Australia) (en-AU)", lang: "en-AU" },
  { name: "Google TTS - English (India) (en-IN)", lang: "en-IN" },
  { name: "Google TTS - Filipino/Tagalog (tl-PH)", lang: "tl-PH" }
];

// ─── Voice dropdown population ───
function populateVoiceDropdown() {
  if (!ttsVoiceSelect) return;
  ttsVoiceSelect.innerHTML = "";
  for (const voice of GTTS_VOICES) {
    const opt = document.createElement("option");
    opt.value = voice.name;
    opt.textContent = voice.name;
    ttsVoiceSelect.appendChild(opt);
  }
  // Restore saved voice
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

// ─── Load saved language, OCR, and TTS preferences ───
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
// ─── Sync settings in real-time when changed elsewhere ───
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

// ─── Save language on change ───
languageSelect.addEventListener("change", () => {
  if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
    chrome.storage.local.set({ preferredLanguage: languageSelect.value });
  }
});

// ─── Save OCR preference on change ───
ocrToggle.addEventListener("change", () => {
  if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
    chrome.storage.local.set({ useOcr: ocrToggle.checked });
  }
});

// ─── Save TTS preference on change & toggle voice row ───
ttsToggle.addEventListener("change", () => {
  if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
    chrome.storage.local.set({ useTts: ttsToggle.checked });
  }
  updateTtsVoiceVisibility();
});

// ─── Save selected voice on change ───
if (ttsVoiceSelect) {
  ttsVoiceSelect.addEventListener("change", () => {
    if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
      chrome.storage.local.set({ selectedVoice: ttsVoiceSelect.value });
    }
  });
}

// ─── Populate language dropdown based on provider ───
function populateLanguages(provider) {
  const languages = LANGUAGE_MAP[provider] || LANGUAGE_MAP.gemini;
  const currentValue = languageSelect.value;

  languageSelect.innerHTML = "";
  for (const lang of languages) {
    const option = document.createElement("option");
    option.value = lang.value;
    option.textContent = lang.label;
    languageSelect.appendChild(option);
  }

  // Restore saved selection if it's still valid for this provider
  const validValues = languages.map((l) => l.value);
  if (validValues.includes(currentValue)) {
    languageSelect.value = currentValue;
  } else {
    languageSelect.value = "english";
    chrome.storage.local.set({ preferredLanguage: "english" });
  }
}

// ─── Fetch settings from backend and configure UI ───
let activeProvider = "ollama";
let activeOllamaModel = "";
let activeGeminiModel = "";
let allOllamaModels = [];
const allGeminiModels = [
  { name: "gemini-2.5-flash", size_bytes: null, modified_at: null },
  { name: "gemini-2.5-pro", size_bytes: null, modified_at: null },
  { name: "gemini-2.0-flash", size_bytes: null, modified_at: null },
  { name: "gemini-2.0-pro-exp-02-05", size_bytes: null, modified_at: null },
  { name: "gemini-1.5-flash", size_bytes: null, modified_at: null },
  { name: "gemini-1.5-pro", size_bytes: null, modified_at: null }
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
    if (settings?.gemini_model) {
      activeGeminiModel = settings.gemini_model;
    }
    if (settings?.ollama_model) {
      activeOllamaModel = settings.ollama_model;
    }

    if (window.updateLlmSelectorUI) {
      window.updateLlmSelectorUI();
    }

    const provider = activeProvider.toLowerCase();

    // Use server-provided language list if available, otherwise use local map
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

// ─── Verdict helpers ───
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

// ─── Load scan history ───
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

// ─── Initialize ───
loadSettings();
loadHistory();
initModelSelector();

// ---------- Custom Dropdowns Selector for Extension Popup ----------
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

  // Toggle dropdown on click for model selector
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

  // Close dropdown on outside click
  document.addEventListener("click", (e) => {
    if (!container.contains(e.target)) {
      trigger.classList.remove("open");
      dropdown.classList.remove("visible");
      trigger.setAttribute("aria-expanded", "false");
    }
  });

  // Handle search filtering
  searchInput.addEventListener("input", (e) => {
    renderModelList(e.target.value);
  });

  // Prevent dropdown closing when clicking inside search input
  searchInput.addEventListener("click", (e) => {
    e.stopPropagation();
  });

  // Toggle dropdown on click for LLM selector
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

    // Handle clicks on items in LLM list
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
      activeLlmName.textContent = activeProvider === "ollama" ? "Ollama (Local)" : "Gemini (Cloud)";
    }
    const llmItems = llmList?.querySelectorAll(".model-item");
    if (llmItems) {
      llmItems.forEach(item => {
        const val = item.getAttribute("data-value");
        const badge = item.querySelector(".model-item-status-badge");
        if (val === activeProvider) {
          item.classList.add("active-model");
          if (badge) {
            badge.className = "model-item-status-badge status-active";
            badge.textContent = "Active";
          }
        } else {
          item.classList.remove("active-model");
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
      } else {
        badge.style.backgroundColor = "var(--verdict-safe)";
        badge.style.boxShadow = "0 0 8px var(--verdict-safe)";
      }
    }
  }

  window.updateLlmSelectorUI = updateLlmSelectorUI;
  updateLlmSelectorUI();

  await fetchAndRenderModels();

  async function fetchAndRenderModels() {
    if (activeProvider === "ollama") {
      try {
        if (activeNameSpan) activeNameSpan.innerHTML = '<span class="loading-dot" style="display:inline-block; vertical-align:middle; margin-right:4px;"></span> Fetching...';
        if (trigger) trigger.disabled = true;

        const data = await fetch(`${BACKEND}/api/ollama/models`).then(r => r.json());
        
        if (trigger) trigger.disabled = false;
        allOllamaModels = data.models || [];
        activeOllamaModel = data.active_model || "";
        activeVisionModel = data.active_vision_model || "";

        if (data.error) {
          if (statusIndicator) {
            statusIndicator.style.backgroundColor = "var(--verdict-dangerous)";
            statusIndicator.style.boxShadow = "0 0 8px var(--verdict-dangerous)";
          }
        } else {
          if (statusIndicator) {
            statusIndicator.style.backgroundColor = "var(--verdict-safe)";
            statusIndicator.style.boxShadow = "0 0 8px var(--verdict-safe)";
          }
        }
      } catch (err) {
        if (trigger) trigger.disabled = false;
        if (activeNameSpan) activeNameSpan.textContent = "Offline";
        if (statusIndicator) {
          statusIndicator.style.backgroundColor = "var(--verdict-dangerous)";
          statusIndicator.style.boxShadow = "0 0 8px var(--verdict-dangerous)";
        }
      }
    } else {
      if (trigger) trigger.disabled = false;
      if (statusIndicator) {
        statusIndicator.style.backgroundColor = "var(--verdict-safe)";
        statusIndicator.style.boxShadow = "0 0 8px var(--verdict-safe)";
      }
    }
    updateActiveModelUI();
  }

  function updateActiveModelUI() {
    if (!activeNameSpan) return;
    
    if (activeProvider === "ollama") {
      if (activeOllamaModel) {
        activeNameSpan.textContent = cleanModelName(activeOllamaModel);
      } else {
        activeNameSpan.textContent = "Select Model";
      }
    } else {
      if (activeGeminiModel) {
        activeNameSpan.textContent = cleanModelName(activeGeminiModel);
      } else {
        activeNameSpan.textContent = "Select Model";
      }
    }
    renderModelList("");
  }

  function cleanModelName(rawName) {
    if (!rawName) return "Unknown";
    let name = rawName;
    
    if (name.startsWith("gemini-")) {
      if (name.includes("2.5-flash")) return "Gemini 2.5 Flash";
      if (name.includes("2.5-pro")) return "Gemini 2.5 Pro";
      if (name.includes("2.0-flash")) return "Gemini 2.0 Flash";
      if (name.includes("2.0-pro")) return "Gemini 2.0 Pro";
      if (name.includes("1.5-flash")) return "Gemini 1.5 Flash";
      if (name.includes("1.5-pro")) return "Gemini 1.5 Pro";
      return name;
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
    
    const modelsToRender = activeProvider === "ollama" ? allOllamaModels : allGeminiModels;
    const filtered = modelsToRender.filter(m => m.name.toLowerCase().includes(filter));

    if (filtered.length === 0) {
      if (modelsToRender.length === 0) {
        if (activeProvider === "ollama") {
          renderEmptyState("No local Ollama models found.");
        } else {
          renderEmptyState("No Gemini models configured.");
        }
      } else {
        renderEmptyState("No matching models found.");
      }
      return;
    }

    filtered.forEach(model => {
      const activeModelName = activeProvider === "ollama" ? activeOllamaModel : activeGeminiModel;
      const isTxtActive = model.name === activeModelName || model.name.split(":")[0] === activeModelName.split(":")[0];
      const isActive = isTxtActive;

      const item = document.createElement("div");
      item.className = `model-item ${isActive ? 'active-model' : ''}`;
      
      const relativeTime = formatRelativeTime(model.modified_at);

      item.innerHTML = `
        <div class="model-item-info">
          <div class="model-item-header">
            <span class="model-item-name" title="${model.name}">${cleanModelName(model.name)}</span>
            <span class="model-item-status-badge ${isActive ? 'status-active' : 'status-available'}">
              ${isActive ? 'Active' : 'Available'}
            </span>
          </div>
          <div class="model-item-details">
            ${model.size_bytes ? `<span class="model-item-size">${formatSize(model.size_bytes)}</span>` : '<span class="model-item-size">API Cloud</span>'}
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
          } else {
            res = await fetch(`${BACKEND}/api/settings/switch-gemini-model`, {
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
            } else {
              activeGeminiModel = model.name;
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
