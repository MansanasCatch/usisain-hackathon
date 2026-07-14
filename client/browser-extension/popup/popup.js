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
  chrome.tabs.create({ url: `${BACKEND}/app/` });
});

btnDashboard.addEventListener("click", () => {
  chrome.tabs.create({ url: `${BACKEND}/app/dashboard/` });
});

// ─── Load saved language ───
chrome.storage.local.get("preferredLanguage", (data) => {
  if (data.preferredLanguage) {
    languageSelect.value = data.preferredLanguage;
  }
});

// ─── Save language on change ───
languageSelect.addEventListener("change", () => {
  chrome.storage.local.set({ preferredLanguage: languageSelect.value });
});

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
async function loadSettings() {
  try {
    const res = await fetch(`${BACKEND}/api/settings`);
    const settings = await res.json();
    const provider = (settings.default_llm_provider || "ollama").toLowerCase();

    // Update provider badge
    providerName.textContent = provider === "gemini" ? "Gemini" : "Ollama";
    providerBadge.title = `Active LLM: ${provider}`;

    // Use server-provided language list if available, otherwise use local map
    if (settings.supported_languages && settings.supported_languages[provider]) {
      const serverLangs = settings.supported_languages[provider];
      LANGUAGE_MAP[provider] = serverLangs.map((v) => ({
        value: v,
        label: v.charAt(0).toUpperCase() + v.slice(1),
      }));
    }

    populateLanguages(provider);
  } catch {
    // Backend unreachable — default to full list
    providerName.textContent = "Offline";
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
