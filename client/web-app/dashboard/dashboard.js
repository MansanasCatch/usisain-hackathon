import { centerTextPlugin, renderTrendChart, renderVerdictChart, trendChartInstance, verdictChartInstance } from "./modules/charts.js";
import { loadRefDocs, onRefDocFileSelected, bindRefDocsEvents } from "./modules/ref_docs.js";
import { loadErrors, bindErrorLogEvents } from "./modules/error_log.js";
import { loadStepInfo } from "./modules/step_info.js";
import { loadAISettingsTab, bindAISettingsEvents } from "./modules/ai_settings.js";

window.lastTotalScans = 0;
window.onRefDocFileSelected = onRefDocFileSelected;
window.loadRefDocs = loadRefDocs;
window.loadErrors = loadErrors;
window.loadStepInfo = loadStepInfo;
window.loadAISettingsTab = loadAISettingsTab;


document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll("main > section").forEach(s => s.classList.add("hidden"));
    btn.classList.add("active");
    
    const targetSection = document.getElementById(`tab-${btn.dataset.tab}`);
    if (targetSection) {
      targetSection.classList.remove("hidden");
    }
    
    if (btn.dataset.tab === "stepinfo") {
      loadStepInfo();
    } else if (btn.dataset.tab === "aisettings") {
      loadAISettingsTab({ apiClient: window.ApiClient, loadSettingsFn: loadSettings });
    }
  });
});


let pipelineTimeoutSeconds = 120;
let maxReferenceDocSizeMb = 10;
let supportedLanguages = {
  ollama: ["english", "taglish", "tagalog", "cebuano", "bisaya", "ilocano"],
  gemini: ["english", "taglish", "tagalog", "cebuano", "bisaya", "ilocano"],
  grok: ["english", "taglish", "tagalog", "cebuano", "bisaya", "ilocano"],
};
let activeProvider = "ollama";
let activeOllamaModel = "";
let activeGeminiModel = "";
let activeGrokModel = "gpt-oss-120b";

async function loadSettings() {
  try {
    const settings = await ApiClient.getSettings();
    if (settings?.server_ip) {
      const serverIpVal = document.getElementById("server-ip-value");
      if (serverIpVal) {
        serverIpVal.textContent = `${settings.server_ip}:8000`;
      }
    }
    if (settings?.pipeline_step_timeout_seconds) {
      pipelineTimeoutSeconds = Number(settings.pipeline_step_timeout_seconds) || pipelineTimeoutSeconds;
    }
    if (settings?.max_reference_doc_size_mb) {
      maxReferenceDocSizeMb = Number(settings.max_reference_doc_size_mb) || maxReferenceDocSizeMb;
      const hint = document.getElementById("refdoc-max-size-hint");
      if (hint) {
        hint.textContent = `Maximum file size: ${maxReferenceDocSizeMb} MB`;
      }
    }
    if (settings?.supported_languages) {
      supportedLanguages = settings.supported_languages;
    }
    if (settings?.default_llm_provider) {
      activeProvider = settings.default_llm_provider;
      const modalProv = document.getElementById("llm-provider");
      if (modalProv) modalProv.value = activeProvider;
      const settingDefault = document.getElementById("setting-default-provider");
      if (settingDefault) settingDefault.value = activeProvider;
      if (window.updateLlmSelectorUI) {
        window.updateLlmSelectorUI();
      }
    }
    if (settings?.gemini_model) {
      activeGeminiModel = settings.gemini_model;
      const gemSel = document.getElementById("setting-gemini-model");
      if (gemSel) gemSel.value = activeGeminiModel;
    }
    if (settings?.grok_model) {
      activeGrokModel = settings.grok_model;
      const grokSel = document.getElementById("setting-grok-model");
      if (grokSel) grokSel.value = activeGrokModel;
    }
    if (settings?.ollama_model) {
      activeOllamaModel = settings.ollama_model;
      const ollamaSel = document.getElementById("setting-ollama-model");
      if (ollamaSel) ollamaSel.value = activeOllamaModel;
    }
    if (window.updateActiveModelUI) {
      window.updateActiveModelUI();
    }
    if (settings?.tts_enabled !== undefined) {
      document.getElementById("tts-toggle").checked = settings.tts_enabled;
      window.ttsPlayer.setEnabled(settings.tts_enabled);
      populateVoiceDropdown();
      updateVoiceControlsVisibility();
    }
    updateLanguageOptions();
  } catch (err) {
    console.warn("Unable to load settings:", err);
  }
}

function updateVoiceControlsVisibility() {
  const enabled = ttsToggle.checked;
  const voiceRow = document.getElementById("tts-voice-row");
  if (voiceRow) voiceRow.classList.toggle("hidden", !enabled);
  
  let hasCompletedSpeech = false;
  for (let i = 1; i <= 5; i++) {
    const row = document.getElementById(`step-${i}`);
    if (row && row.dataset.speechText) {
      hasCompletedSpeech = true;
      break;
    }
  }
  if (ttsReplay) ttsReplay.classList.toggle("hidden", !(enabled && hasCompletedSpeech));
}

function populateVoiceDropdown() {
  if (!ttsVoice) return;
  ttsVoice.innerHTML = "";
  const voices = window.ttsPlayer.voices || [];
  for (const voice of voices) {
    const opt = document.createElement("option");
    opt.value = voice.name;
    opt.textContent = `${voice.name} (${voice.lang})`;
    ttsVoice.appendChild(opt);
  }
  if (window.ttsPlayer.selectedVoiceName) {
    ttsVoice.value = window.ttsPlayer.selectedVoiceName;
  }
}


async function loadOverview() {
  try {
    const summary = await ApiClient.getSummary();
    
    
    const verdicts = summary.by_verdict || {};
    const safeCount = (verdicts.likely_true || 0) + (verdicts.likely_authentic || 0);
    const warnCount = verdicts.inconclusive || 0;
    const badCount = (verdicts.flagged || 0) + (verdicts.likely_edited || 0) + (verdicts.likely_ai_generated || 0);

    
    document.getElementById("val-total-scans").textContent = summary.total_scans || 0;
    document.getElementById("val-safe-scans").textContent = safeCount;
    document.getElementById("val-warn-scans").textContent = warnCount;
    document.getElementById("val-bad-scans").textContent = badCount;
    window.lastTotalScans = summary.total_scans || 0;

    
    const trend = await ApiClient.getTrends(30);
    const days = [...new Set(trend.map(t => t.day))].sort();
    const channels = [...new Set(trend.map(t => t.channel))];
    
    
    const colors = { extension: "#6366f1", webapp: "#f59e0b", api: "#10b981" };
    const chartColorsGlow = {
      extension: "rgba(99, 102, 241, 0.15)",
      webapp: "rgba(245, 158, 11, 0.15)",
      api: "rgba(16, 185, 129, 0.15)"
    };

    renderTrendChart(days, channels, trend);
    renderVerdictChart(verdicts);

  } catch (err) {
    console.error("Dashboard visualization error:", err);
    document.getElementById("trend-chart").parentElement.innerHTML = `<div style="padding:40px; text-align:center; color:var(--muted)">Visualization unavailable: ${err.message}</div>`;
    document.getElementById("verdict-chart").parentElement.innerHTML = `<div style="padding:40px; text-align:center; color:var(--muted)">Verdict distribution unavailable: ${err.message}</div>`;
  }
}


async function loadScans() {
  const channel = document.getElementById("filter-channel").value;
  const limit = document.getElementById("limit-scans").value;
  const searchQuery = document.getElementById("search-scans").value.toLowerCase();
  
  
  const fetchLimit = searchQuery ? 100 : Number(limit);
  const scans = await ApiClient.getScans({ channel, limit: fetchLimit });
  const tbody = document.querySelector("#scans-table tbody");
  tbody.innerHTML = "";

  
  const filteredScans = scans.filter(s => {
    if (!searchQuery) return true;
    const summary = (s.input_summary || "").toLowerCase();
    const verdict = (s.step3_verdict || "").toLowerCase();
    const type = (s.content_type || "").toLowerCase();
    return summary.includes(searchQuery) || verdict.includes(searchQuery) || type.includes(searchQuery);
  });

  
  const displayScans = filteredScans.slice(0, Number(limit));

  if (displayScans.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding: 40px; color: var(--muted-light);">No scans matching current filters.</td></tr>`;
    return;
  }

  for (const s of displayScans) {
    const tr = document.createElement("tr");
    const scoreVal = s.step2_score !== null && s.step2_score !== undefined ? s.step2_score : "—";
    
    tr.innerHTML = `
      <td>${new Date(s.created_at + "Z").toLocaleString()}</td>
      <td><span style="font-weight: 500; font-size:12px;">${s.channel.toUpperCase()}</span></td>
      <td><span style="color: var(--muted-light);">${s.content_type ?? "—"}</span></td>
      <td style="max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${s.input_summary || "—"}</td>
      <td><strong style="color: ${scoreVal !== "—" ? 'var(--accent-light)' : 'inherit'};">${scoreVal}</strong></td>
      <td><span class="badge ${s.step3_verdict}">${(s.step3_verdict || "—").replace(/_/g, " ")}</span></td>`;
    
    tr.addEventListener("click", () => openModal(s.raw_result_json));
    tbody.appendChild(tr);
  }
}


document.getElementById("refresh-scans").addEventListener("click", loadScans);
document.getElementById("filter-channel").addEventListener("change", loadScans);
document.getElementById("limit-scans").addEventListener("change", loadScans);
document.getElementById("search-scans").addEventListener("input", loadScans);

document.getElementById("clear-scans").addEventListener("click", async () => {
  if (confirm("Are you sure you want to clear all scan history? This will also clear the local RAG database cache.")) {
    await ApiClient.clearScans();
    loadScans();
    loadOverview();
  }
});


function openModal(rawJson) {
  try {
    document.getElementById("modal-body").textContent = JSON.stringify(JSON.parse(rawJson), null, 2);
  } catch (e) {
    document.getElementById("modal-body").textContent = rawJson;
  }
  document.getElementById("detail-modal").classList.add("open");
}

document.getElementById("modal-close").addEventListener("click", () => {
  document.getElementById("detail-modal").classList.remove("open");
});


bindRefDocsEvents(() => maxReferenceDocSizeMb, ApiClient);


bindErrorLogEvents(openModal, ApiClient);



const STEP_LABELS = {
  1: "AI Insights", 2: "Content Analyser", 3: "Authenticity",
  4: "Actionable Items", 5: "Learnings",
};

const STEP_ICONS = { 1: "💡", 2: "🔬", 3: "✅", 4: "🎯", 5: "📚" };

const STEP_START_MESSAGES = {
  english: {
    1: "Starting Step 1, AI Insights.",
    2: "Starting Step 2, Content Analyser.",
    3: "Starting Step 3, Authenticity check.",
    4: "Starting Step 4, Actionable Items.",
    5: "Starting Step 5, Learnings and educational resources."
  },
  taglish: {
    1: "Sinisimulan ang step 1, AI Insights.",
    2: "Sinisimulan ang step 2, Content Analyser.",
    3: "Sinisimulan ang step 3, Authenticity check.",
    4: "Sinisimulan ang step 4, Actionable Items.",
    5: "Sinisimulan ang step 5, Learnings and educational resources."
  },
  tagalog: {
    1: "Sinisimulan ang unang hakbang, AI Insights.",
    2: "Sinisimulan ang ikalawang hakbang, Content Analyser.",
    3: "Sinisimulan ang ikatlong hakbang, Authenticity check.",
    4: "Sinisimulan ang ika-apat na hakbang, Actionable Items.",
    5: "Sinisimulan ang ikalimang hakbang, Learnings."
  },
  cebuano: {
    1: "Nagsugod sa unang lakang, AI Insights.",
    2: "Nagsugod sa ikaduhang lakang, Content Analyser.",
    3: "Nagsugod sa ikatlong lakang, Authenticity check.",
    4: "Nagsugod sa ika-upat nga lakang, Actionable Items.",
    5: "Nagsugod sa ikalimang lakang, Learnings."
  },
  bisaya: {
    1: "Nagsugod sa unang lakang, AI Insights.",
    2: "Nagsugod sa ikaduhang lakang, Content Analyser.",
    3: "Nagsugod sa ikatlong lakang, Authenticity check.",
    4: "Nagsugod sa ika-upat nga lakang, Actionable Items.",
    5: "Nagsugod sa ikalimang lakang, Learnings."
  },
  ilocano: {
    1: "Mairugi ti umuna a tukad, AI Insights.",
    2: "Mairugi ti maikadua a tukad, Content Analyser.",
    3: "Mairugi ti maikatlo a tukad, Authenticity check.",
    4: "Mairugi ti maikapat a tukad, Actionable Items.",
    5: "Mairugi ti maikalima a tukad, Learnings."
  }
};

const openAnalyzeBtn = document.getElementById("header-analyze-btn");
const analyzeModal = document.getElementById("analyze-modal");
const analyzeModalClose = document.getElementById("analyze-modal-close");
const inputStage = document.getElementById("analyze-input-stage");
const progressStage = document.getElementById("analyze-progress-stage");
const modeSelect = document.getElementById("content-mode");
const textInput = document.getElementById("text-input");
const fileInput = document.getElementById("file-input");
const providerSelect = document.getElementById("llm-provider");
const languageSelect = document.getElementById("language");
const ttsToggle = document.getElementById("tts-toggle");
const ttsVoice = document.getElementById("tts-voice");
const ttsReplay = document.getElementById("tts-replay");
const ocrToggle = document.getElementById("ocr-toggle");
const dropZone = document.getElementById("drop-zone");
const previewContainer = document.getElementById("file-preview-container");
const previewImg = document.getElementById("file-preview-img");
const removePreviewBtn = document.getElementById("remove-preview-btn");
const analyzeForm = document.getElementById("analyze-form");
const submitBtn = document.getElementById("submit-btn");
const doneBtn = document.getElementById("analysis-done-btn");
const cancelVoiceBtn = document.getElementById("cancel-voice-btn");
const progressLine = document.getElementById("pipeline-progress-line");
const errorBanner = document.getElementById("error-banner");
const pipelineSpinner = document.getElementById("pipeline-spinner");

function openAnalyzeModal() {
  analyzeModal.classList.add("open");
  resetAnalyzeModal();
}

function closeAnalyzeModal() {
  analyzeModal.classList.remove("open");
  window.ttsPlayer.stop();
  
  loadOverview();
  loadScans();
  loadErrors();
}

openAnalyzeBtn.addEventListener("click", openAnalyzeModal);
analyzeModalClose.addEventListener("click", closeAnalyzeModal);
doneBtn.addEventListener("click", closeAnalyzeModal);

cancelVoiceBtn.addEventListener("click", () => {
  window.ttsPlayer.stop();
  cancelVoiceBtn.classList.add("hidden");
});


dropZone.addEventListener("click", () => fileInput.click());


dropZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropZone.classList.add("dragover");
});

dropZone.addEventListener("dragleave", () => {
  dropZone.classList.remove("dragover");
});

dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZone.classList.remove("dragover");
  if (e.dataTransfer.files.length > 0) {
    fileInput.files = e.dataTransfer.files;
    handleFileSelected(fileInput.files[0]);
  }
});

fileInput.addEventListener("change", () => {
  if (fileInput.files.length > 0) {
    handleFileSelected(fileInput.files[0]);
  }
});

removePreviewBtn.addEventListener("click", () => {
  clearFileSelection();
});

let cameraStream = null;
let capturedImageBlob = null;

async function startCamera() {
  const video = document.getElementById("camera-video");
  const captureBtn = document.getElementById("camera-capture-btn");
  const retryBtn = document.getElementById("camera-retry-btn");
  
  if (!video) return;

  capturedImageBlob = null;
  if (captureBtn) captureBtn.classList.remove("hidden");
  if (retryBtn) retryBtn.classList.add("hidden");
  video.classList.remove("hidden");
  previewContainer.classList.add("hidden");

  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "environment" }
    });
    video.srcObject = cameraStream;
  } catch (err) {
    console.error("Camera access failed:", err);
    const container = document.getElementById("camera-container");
    if (container) {
      const errorDiv = document.createElement("div");
      errorDiv.id = "camera-error-msg";
      errorDiv.className = "dashboard-camera-error";
      errorDiv.textContent = "Could not access camera/webcam. Please check permissions or upload a file instead.";
      const oldErr = document.getElementById("camera-error-msg");
      if (oldErr) oldErr.remove();
      container.appendChild(errorDiv);
    }
  }
}

function stopCamera() {
  if (cameraStream) {
    cameraStream.getTracks().forEach(track => track.stop());
    cameraStream = null;
  }
  const video = document.getElementById("camera-video");
  if (video) video.srcObject = null;
  const oldErr = document.getElementById("camera-error-msg");
  if (oldErr) oldErr.remove();
}

function capturePhoto() {
  const video = document.getElementById("camera-video");
  const canvas = document.getElementById("camera-canvas");
  const captureBtn = document.getElementById("camera-capture-btn");
  const retryBtn = document.getElementById("camera-retry-btn");

  if (!video || !canvas) return;

  const ctx = canvas.getContext("2d");
  canvas.width = video.videoWidth || 640;
  canvas.height = video.videoHeight || 480;

  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  
  canvas.toBlob(blob => {
    capturedImageBlob = blob;
    
    video.classList.add("hidden");
    if (captureBtn) captureBtn.classList.add("hidden");
    if (retryBtn) retryBtn.classList.remove("hidden");
    
    previewImg.src = URL.createObjectURL(blob);
    previewContainer.classList.remove("hidden");
    
    stopCamera();
  }, "image/jpeg", 0.85);
}

function handleFileSelected(file) {
  if (!file) return;
  
  if (file.type.startsWith("image/")) {
    const reader = new FileReader();
    reader.onload = (e) => {
      previewImg.src = e.target.result;
      previewContainer.classList.remove("hidden");
      dropZone.classList.add("hidden");
    };
    reader.readAsDataURL(file);
  }
}

function clearFileSelection() {
  fileInput.value = "";
  previewImg.src = "";
  previewContainer.classList.add("hidden");
  capturedImageBlob = null;
  
  const mode = modeSelect.value;
  if (mode === "image") {
    dropZone.classList.remove("hidden");
  } else if (mode === "camera") {
    const container = document.getElementById("camera-container");
    if (container) container.classList.remove("hidden");
    startCamera();
  }
}

function resetAnalyzeModal() {
  inputStage.classList.remove("hidden");
  progressStage.classList.add("hidden");
  doneBtn.classList.add("hidden");
  cancelVoiceBtn.classList.add("hidden");
  errorBanner.classList.add("hidden");
  errorBanner.textContent = "";
  pipelineSpinner.classList.remove("hidden");
  submitBtn.disabled = false;
  
  textInput.value = "";
  clearFileSelection();
  updateFormFields();
  
  window.ttsPlayer.stop();
  for (let i = 1; i <= 5; i++) {
    const row = document.getElementById(`step-${i}`);
    if (row) {
      delete row.dataset.speechText;
    }
  }
  updateVoiceControlsVisibility();
}

function updateLanguageOptions() {
  const provider = providerSelect.value || "gemini";
  const allowed = supportedLanguages[provider] || supportedLanguages.gemini;
  const currentValue = languageSelect.value;

  languageSelect.innerHTML = "";
  for (const lang of allowed) {
    const option = document.createElement("option");
    option.value = lang;
    option.textContent = lang.charAt(0).toUpperCase() + lang.slice(1);
    languageSelect.appendChild(option);
  }

  if (allowed.includes(currentValue)) {
    languageSelect.value = currentValue;
  } else {
    languageSelect.value = "english";
  }
}

providerSelect.addEventListener("change", updateLanguageOptions);

function updateFormFields() {
  const mode = modeSelect.value;
  const cameraContainer = document.getElementById("camera-container");
  
  textInput.classList.toggle("hidden", mode !== "text");
  dropZone.classList.toggle("hidden", mode !== "image");
  
  if (cameraContainer) {
    cameraContainer.classList.toggle("hidden", mode !== "camera");
  }

  if (mode === "camera") {
    startCamera();
  } else {
    stopCamera();
  }
  
  textInput.placeholder = "Paste the claim or message to check...";

  clearFileSelection();
}

modeSelect.addEventListener("change", updateFormFields);


const captureBtnElement = document.getElementById("camera-capture-btn");
const retryBtnElement = document.getElementById("camera-retry-btn");
if (captureBtnElement) captureBtnElement.addEventListener("click", capturePhoto);
if (retryBtnElement) retryBtnElement.addEventListener("click", () => clearFileSelection());

ttsToggle.addEventListener("change", (e) => {
  window.ttsPlayer.setEnabled(e.target.checked);
  updateVoiceControlsVisibility();
});

ttsVoice.addEventListener("change", (e) => {
  window.ttsPlayer.selectedVoiceName = e.target.value;
});

ttsReplay.addEventListener("click", () => {
  window.ttsPlayer.stop();
  for (let i = 1; i <= 5; i++) {
    const row = document.getElementById(`step-${i}`);
    if (row && row.dataset.speechText) {
      window.ttsPlayer.speak(row.dataset.speechText);
    }
  }
});


const activeTimers = {};

function clearTimerForStep(step) {
  if (activeTimers[step]) {
    clearInterval(activeTimers[step]);
    delete activeTimers[step];
  }
}

function setStepRowStatus(step, status, iconText, bodyHtml, color) {
  const row = document.getElementById(`step-${step}`);
  if (!row) return;
  const indicator = row.querySelector(".step-status-indicator");
  const body = row.querySelector(".step-body");
  
  row.dataset.status = status;
  
  if (indicator) {
    if (status === "error") {
      indicator.className = "step-status-indicator status-error";
      indicator.textContent = "✕";
    } else if (status === "completed") {
      indicator.className = "step-status-indicator status-completed";
      indicator.textContent = "✓";
    } else if (status === "in_progress") {
      indicator.className = "step-status-indicator status-in-progress";
      indicator.textContent = STEP_ICONS[step] || "⏳";
    } else {
      indicator.className = "step-status-indicator status-waiting";
      indicator.textContent = step;
    }
  }
  
  body.innerHTML = bodyHtml;
}

function updatePipelineNode(step, status) {
  const node = document.getElementById(`node-${step}`);
  if (!node) return;
  node.className = "pipeline-node " + status;
  
  
  let pct = 0;
  if (status === "active") {
    pct = (step - 1) * 20 + 10;
  } else if (status === "completed") {
    pct = step * 20;
  } else if (status === "error") {
    pct = (step - 1) * 20 + 10;
  }
  if (progressLine) {
    progressLine.style.width = `${pct}%`;
  }
}

function markFollowingStepsFailed(startStep) {
  for (let step = startStep; step <= 5; step++) {
    const row = document.getElementById(`step-${step}`);
    if (!row || (row.dataset.status !== "pending" && row.dataset.status !== "in_progress")) continue;
    clearTimerForStep(step);
    setStepRowStatus(step, "error", "✕", formatContent("Skipped because a previous step failed."));
    updatePipelineNode(step, "error");
  }
}

function initStepRows() {
  inputStage.classList.add("hidden");
  progressStage.classList.remove("hidden");
  document.getElementById("results-header").textContent = "Analyzing…";
  errorBanner.classList.add("hidden");
  errorBanner.textContent = "";
  
  
  const previewTextContainer = document.getElementById("analysis-preview-text");
  const previewMediaContainer = document.getElementById("analysis-preview-media");
  const previewThumb = document.getElementById("analysis-preview-thumbnail");
  const successCheck = document.getElementById("pipeline-success-check");
  
  if (successCheck) successCheck.classList.add("hidden");
  if (pipelineSpinner) pipelineSpinner.classList.remove("hidden");

  const mode = modeSelect.value;
  if (mode === "text") {
    if (previewMediaContainer) previewMediaContainer.classList.add("hidden");
    if (previewTextContainer) {
      previewTextContainer.textContent = textInput.value ? `"${textInput.value}"` : "";
      previewTextContainer.classList.remove("hidden");
    }
  } else {
    if (previewMediaContainer) previewMediaContainer.classList.remove("hidden");
    if (previewThumb && previewImg) {
      previewThumb.src = previewImg.src || "";
    }
    if (previewTextContainer) {
      previewTextContainer.textContent = mode === "camera" ? "Camera Capture" : (fileInput.files[0]?.name || "Uploaded Image");
      previewTextContainer.classList.remove("hidden");
    }
  }

  if (progressLine) progressLine.style.width = "0%";

  for (let step = 1; step <= 5; step++) {
    clearTimerForStep(step);
    
    
    const node = document.getElementById(`node-${step}`);
    if (node) node.className = "pipeline-node";
    
    const row = document.getElementById(`step-${step}`);
    row.dataset.status = "pending";
    row.style.cssText = ``;
    row.innerHTML = `
      <div class="step-status-indicator status-waiting">${step}</div>
      <div style="flex:1;">
        <div class="step-label">
          <span class="step-num">STEP ${step}</span>
          ${STEP_LABELS[step]}
        </div>
        <div class="step-body" style="white-space:pre-wrap;">Waiting…</div>
        <div class="step-progress-track"><div class="step-progress-bar"></div></div>
      </div>`;
  }
}

function formatContent(text) {
  if (!text) return "";
  let escaped = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");

  escaped = escaped.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, (match, linkText, url) => {
    return `<a href="${url}" target="_blank" style="color:var(--accent-light); text-decoration:underline; word-break:break-all;">${linkText}</a>`;
  });

  escaped = escaped.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  return escaped.replace(/\n/g, "<br>");
}

function updateStepRow(event) {
  const row = document.getElementById(`step-${event.step}`);
  if (!row) return;
  const indicator = row.querySelector(".step-status-indicator");
  const body = row.querySelector(".step-body");

  clearTimerForStep(event.step);

  if (event.status === "in_progress") {
    if (indicator) {
      indicator.className = "step-status-indicator status-in-progress";
      indicator.textContent = STEP_ICONS[event.step] || "⏳";
    }
    row.dataset.status = "in_progress";
    updatePipelineNode(event.step, "active");
    
    let secondsLeft = pipelineTimeoutSeconds;
    body.textContent = `Analyzing… ${secondsLeft}s remaining`;
    
    const lang = languageSelect.value;
    const startMsgs = STEP_START_MESSAGES[lang] || STEP_START_MESSAGES.english;
    const startMsg = startMsgs[event.step] || `Starting step ${event.step}`;
    window.ttsPlayer.speak(startMsg);

    activeTimers[event.step] = setInterval(() => {
      secondsLeft--;
      if (secondsLeft <= 0) {
        clearTimerForStep(event.step);
        if (row.dataset.status === "in_progress") {
          setStepRowStatus(event.step, "error", "⚠️", formatContent(`Step timed out after ${pipelineTimeoutSeconds} seconds.`), "var(--bad)");
          updatePipelineNode(event.step, "error");
          markFollowingStepsFailed(event.step + 1);
        }
      } else {
        body.textContent = `Analyzing… ${secondsLeft}s remaining`;
      }
    }, 1000);
  } else if (event.status === "error") {
    if (indicator) {
      indicator.className = "step-status-indicator status-error";
      indicator.textContent = "✕";
    }
    row.dataset.status = "error";
    updatePipelineNode(event.step, "error");
    body.innerHTML = formatContent(event.result?.error || "Something went wrong on this step.");
    markFollowingStepsFailed(event.step + 1);

    window.ttsPlayer.speak(`Step ${event.step} failed. ${event.result?.error || ""}`);
  } else if (event.status === "completed") {
    if (indicator) {
      indicator.className = "step-status-indicator status-completed";
      indicator.textContent = "✓";
    }
    row.dataset.status = "completed";
    updatePipelineNode(event.step, "completed");
    body.innerHTML = formatContent(summarizeStep(event.step, event.result));

    const lang = languageSelect.value;
    window.ttsPlayer.setLanguage(lang);
    let speechText = summarizeStep(event.step, event.result);
    if (event.step === 2 && event.result.applicable !== false) {
      speechText = `Visual analysis breakdown: ${event.result.real_pct}% real, ${event.result.edited_pct}% edited, and ${event.result.ai_generated_pct}% AI-generated. ${event.result.explanation}`;
    } else if (event.step === 3) {
      speechText = `Verdict: ${event.result.verdict}. Credibility score: ${event.result.score} out of 100. ${event.result.explanation}`;
    } else if (event.step === 4) {
      speechText = `Here are the actionable items: ${(event.result.actions || []).join(". ")}`;
    }
    row.dataset.speechText = speechText;
    updateVoiceControlsVisibility();
    window.ttsPlayer.speak(speechText);
    
    if (ttsToggle.checked) {
      cancelVoiceBtn.classList.remove("hidden");
    }
  }
}

function summarizeStep(step, result) {
  if (!result) return "Done.";
  if (step === 1) return result.insight || "No insight generated.";
  if (step === 2) {
    if (result.applicable === false) return result.explanation;
    return `${result.real_pct}% real · ${result.edited_pct}% edited · ${result.ai_generated_pct}% AI-generated\n\n${result.explanation || ""}`;
  }
  if (step === 3) return `${result.verdict} (score ${result.score}/100)\n\n${result.explanation || ""}`;
  if (step === 4) return (result.actions || []).map(a => `• ${a}`).join("\n") || "No actions generated.";
  if (step === 5) {
    return result.learning_material || "No learnings generated.";
  }
  return "Done.";
}

async function resizeImageFile(file, maxDim = 1024, quality = 0.75) {
  return new Promise((resolve, reject) => {
    try {
      const img = new Image();
      const url = URL.createObjectURL(file);
      img.onload = () => {
        try {
          let { width, height } = img;
          const maxSide = Math.max(width, height);
          let scale = 1;
          if (maxSide > maxDim) scale = maxDim / maxSide;
          if (scale >= 1) {
            URL.revokeObjectURL(url);
            resolve(file);
            return;
          }

          const canvas = document.createElement('canvas');
          canvas.width = Math.round(width * scale);
          canvas.height = Math.round(height * scale);
          const ctx = canvas.getContext('2d');
          ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

          canvas.toBlob((blob) => {
            URL.revokeObjectURL(url);
            if (!blob) return reject(new Error('Image compression failed'));
            resolve(new File([blob], file.name, { type: 'image/jpeg' }));
          }, 'image/jpeg', quality);
        } catch (err) {
          URL.revokeObjectURL(url);
          reject(err);
        }
      };
      img.onerror = (e) => {
        URL.revokeObjectURL(url);
        reject(e || new Error('Image load error'));
      };
      img.src = url;
    } catch (err) {
      reject(err);
    }
  });
}

analyzeForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  submitBtn.disabled = true;
  initStepRows();

  const mode = modeSelect.value;
  const language = languageSelect.value;
  
  window.ttsPlayer.setLanguage(language);
  window.ttsPlayer.stop();

  const provider = providerSelect.value || "ollama";
  const useOcr = ocrToggle ? ocrToggle.checked : true;
  const formData = new FormData();
  formData.append("language", language);
  formData.append("provider", provider);
  formData.append("use_ocr", useOcr.toString());
  formData.append("source_url", location.href);

  if (mode === "text") {
    formData.append("text", textInput.value);
  } else if (mode === "image") {
    if (!fileInput.files[0]) { submitBtn.disabled = false; resetAnalyzeModal(); return; }
    const file = fileInput.files[0];
    if (file.type && file.type.startsWith("image/")) {
      try {
        const resized = await resizeImageFile(file, 1024, 0.75);
        formData.append("file", resized, file.name);
      } catch (err) {
        formData.append("file", file);
      }
    } else {
      formData.append("file", file);
    }
  } else if (mode === "camera") {
    if (!capturedImageBlob) { submitBtn.disabled = false; resetAnalyzeModal(); return; }
    const capturedFile = new File([capturedImageBlob], "camera_capture.jpg", { type: "image/jpeg" });
    try {
      const resized = await resizeImageFile(capturedFile, 1024, 0.75);
      formData.append("file", resized, "camera_capture.jpg");
    } catch (err) {
      formData.append("file", capturedFile);
    }
  }

  try {
    await streamAnalyze(formData, (event) => {
      if (event.done) {
        document.getElementById("results-header").textContent = `Done — scan #${event.scan_id}`;
        pipelineSpinner.classList.add("hidden");
        const successCheck = document.getElementById("pipeline-success-check");
        if (successCheck) successCheck.classList.remove("hidden");
        doneBtn.classList.remove("hidden");
        
        loadOverview();
        loadScans();
        loadErrors();
        return;
      }
      if (event.systemError) {
        document.getElementById("results-header").textContent = "Error in System Pipeline";
        pipelineSpinner.classList.add("hidden");
        const successCheck = document.getElementById("pipeline-success-check");
        if (successCheck) successCheck.classList.add("hidden");
        
        errorBanner.classList.remove("hidden");
        errorBanner.textContent = "⚠️ System Error: " + event.systemError;
        
        doneBtn.classList.remove("hidden");
        
        loadOverview();
        loadScans();
        loadErrors();
        return;
      }
      updateStepRow(event);
    });
  } catch (err) {
    document.getElementById("results-header").textContent = `Critical Error`;
    pipelineSpinner.classList.add("hidden");
    const successCheck = document.getElementById("pipeline-success-check");
    if (successCheck) successCheck.classList.add("hidden");
    errorBanner.classList.remove("hidden");
    errorBanner.textContent = "⚠️ " + err.message;
    doneBtn.classList.remove("hidden");
    
    loadOverview();
    loadScans();
    loadErrors();
  } finally {
    submitBtn.disabled = false;
  }
});

const urlParams = new URLSearchParams(window.location.search);
if (urlParams.get("analyze") === "true") {
  openAnalyzeModal();
  window.history.replaceState({}, document.title, window.location.pathname);
}


if (window.ttsPlayer) {
  window.ttsPlayer.initVoices();
}
populateVoiceDropdown();
loadSettings();
loadOverview();
loadScans();

// Bind tab event handlers
if (typeof bindAISettingsEvents === "function") {
  bindAISettingsEvents({ apiClient: window.ApiClient, loadSettingsFn: loadSettings });
}
if (typeof bindRefDocsEvents === "function") {
  bindRefDocsEvents({ apiClient: window.ApiClient });
}
if (typeof bindErrorLogEvents === "function") {
  bindErrorLogEvents(undefined, window.ApiClient);
}

loadRefDocs(window.ApiClient);
loadErrors(undefined, window.ApiClient);
initModelSelector();
initPWAServiceWorker();

function initPWAServiceWorker() {
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/app/sw.js?v=3')
        .then(reg => {
          console.log('[PWA] Service Worker registered with scope:', reg.scope);
        })
        .catch(err => {
          console.error('[PWA] Service Worker registration failed:', err);
        });
    });
  }
}

window.addEventListener('resize', () => {
  const isMobile = window.innerWidth < 550;
  const isTablet = window.innerWidth < 650;
  
  try {
    if (typeof trendChartInstance !== 'undefined' && trendChartInstance) {
      trendChartInstance.options.plugins.legend.labels.font.size = isMobile ? 9 : 11;
      trendChartInstance.options.scales.x.ticks.font.size = isMobile ? 8 : 10;
      trendChartInstance.options.scales.y.ticks.font.size = isMobile ? 8 : 10;
      trendChartInstance.update('none');
    }
  } catch (e) {}
  
  try {
    if (typeof verdictChartInstance !== 'undefined' && verdictChartInstance) {
      verdictChartInstance.options.plugins.legend.position = isTablet ? 'bottom' : 'right';
      verdictChartInstance.options.plugins.legend.labels.font.size = isMobile ? 9 : 10;
      verdictChartInstance.options.plugins.legend.labels.padding = isMobile ? 6 : 10;
      verdictChartInstance.update('none');
    }
  } catch (e) {}
});

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
let activeVisionModel = "";

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
        await switchActiveProvider(newProvider);
      });
    });
  }

  async function switchActiveProvider(newProvider) {
    if (!newProvider) return;
    if (newProvider === activeProvider) return;

    if (overlay) {
      overlay.querySelector(".loading-text").textContent = `Switching to ${newProvider.toUpperCase()}...`;
      overlay.classList.add("show");
    }

    try {
      const res = await ApiClient.switchProvider(newProvider);
      if (res && res.status === "ok") {
        activeProvider = newProvider;
        showToast(`Switched active provider to <strong>${newProvider.toUpperCase()}</strong>`);
        
        const modalLlm = document.getElementById("llm-provider");
        if (modalLlm) {
          modalLlm.value = newProvider;
          modalLlm.dispatchEvent(new Event("change"));
        }
        
        const settingDefault = document.getElementById("setting-default-provider");
        if (settingDefault) {
          settingDefault.value = newProvider;
        }

        updateLlmSelectorUI();
        
        await loadSettings();
        await fetchAndRenderModels();
      } else {
        showToast("Failed to switch active provider", true);
      }
    } catch (err) {
      console.error("Error switching provider:", err);
      showToast("Network error switching active provider", true);
    } finally {
      if (overlay) overlay.classList.remove("show");
    }
  }

  window.switchActiveProvider = switchActiveProvider;

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
    const settingDefault = document.getElementById("setting-default-provider");
    if (settingDefault && activeProvider) {
      settingDefault.value = activeProvider;
    }
    const modalProv = document.getElementById("llm-provider");
    if (modalProv && activeProvider) {
      modalProv.value = activeProvider;
    }
    const llmItems = llmList?.querySelectorAll(".model-item");
    if (llmItems) {
      llmItems.forEach(item => {
        const val = item.getAttribute("data-value");
        const check = item.querySelector(".model-item-check");
        const badge = item.querySelector(".model-item-status-badge");
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
      badge.className = "llm-provider-badge";
      if (activeProvider === "ollama") {
        badge.classList.add("llm-ollama");
      } else if (activeProvider === "gemini") {
        badge.classList.add("llm-gemini");
      } else if (activeProvider === "grok") {
        badge.classList.add("llm-grok");
      }
    }
  }

  window.updateLlmSelectorUI = updateLlmSelectorUI;

  updateLlmSelectorUI();

  const modalLlm = document.getElementById("llm-provider");
  if (modalLlm) {
    modalLlm.addEventListener("change", (e) => {
      const newProvider = e.target.value;
      if (newProvider !== activeProvider) {
        const targetItem = llmList?.querySelector(`.model-item[data-value="${newProvider}"]`);
        if (targetItem) targetItem.click();
      }
    });
  }

  await fetchAndRenderModels();

  async function fetchAndRenderModels() {
    if (activeProvider === "ollama") {
      try {
        if (activeNameSpan) activeNameSpan.innerHTML = '<span class="loading-dot" style="display:inline-block; vertical-align:middle; margin-right:4px;"></span> Fetching...';
        if (trigger) trigger.disabled = true;

        const data = await ApiClient.getOllamaModels();
        
        if (trigger) trigger.disabled = false;
        allOllamaModels = data.models || [];
        activeOllamaModel = data.active_model || "";
        activeVisionModel = data.active_vision_model || "";

        if (data.error) {
          console.warn("Ollama model API returned error status:", data.error);
          if (statusIndicator) {
            statusIndicator.style.backgroundColor = "var(--bad)";
            statusIndicator.style.boxShadow = "0 0 8px var(--bad)";
          }
        } else {
          if (statusIndicator) {
            statusIndicator.style.backgroundColor = "var(--good)";
            statusIndicator.style.boxShadow = "0 0 8px var(--good)";
          }
        }
      } catch (err) {
        if (trigger) trigger.disabled = false;
        if (activeNameSpan) activeNameSpan.textContent = "Offline";
        if (statusIndicator) {
          statusIndicator.style.backgroundColor = "var(--bad)";
          statusIndicator.style.boxShadow = "0 0 8px var(--bad)";
        }
        console.error("Failed to load Ollama models:", err);
      }
    } else if (activeProvider === "gemini") {
      if (trigger) trigger.disabled = false;
      if (statusIndicator) {
        statusIndicator.style.backgroundColor = "var(--good)";
        statusIndicator.style.boxShadow = "0 0 8px var(--good)";
      }
    } else if (activeProvider === "grok") {
      if (trigger) trigger.disabled = false;
      try {
        const grokData = await ApiClient.getGrokModels();
        if (grokData?.models && grokData.models.length > 0) {
          allGrokModels = grokData.models;
        }
        if (grokData?.active_model) {
          activeGrokModel = grokData.active_model;
        }
      } catch (err) {
        console.warn("Using default grok models list:", err);
      }
      if (statusIndicator) {
        statusIndicator.style.backgroundColor = "var(--good)";
        statusIndicator.style.boxShadow = "0 0 8px var(--good)";
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

    if (name === "gpt-oss-120b" || name === "openai/gpt-oss-120b" || name.endsWith("gpt-oss-120b")) return "GPT OSS 120B";
    if (name === "gpt-oss-20b" || name === "openai/gpt-oss-20b" || name.endsWith("gpt-oss-20b")) return "GPT OSS 20B";
    if (name.includes("qwen3.8-27b")) return "Qwen 3.8 27B";
    if (name.includes("allam-2-7b")) return "Allam 2 7B";

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
      const parts = name.split(":");
      name = parts[0];
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
      const diffHours = Math.round(diffMs / 3600000);
      const diffDays = Math.round(diffMs / 86400000);
      
      if (diffMins < 1) return "Just now";
      if (diffMins < 60) return `${diffMins}m ago`;
      if (diffHours < 24) return `${diffHours}h ago`;
      if (diffDays < 30) return `${diffDays}d ago`;
      
      return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    } catch (e) {
      return "";
    }
  }

  function isVisionModel(name, provider) {
    if (!name) return false;
    const p = (provider || activeProvider || "").toLowerCase();
    if (p === "gemini") return true;
    const lower = name.toLowerCase();
    const visionKeywords = ["vision", "moondream", "llava", "bakllava", "minicpm-v", "scout", "multimodal", "-vl", "vl-", "_vl"];
    return visionKeywords.some(kw => lower.includes(kw));
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
          renderEmptyState("No local Ollama models found. Pull models with `ollama pull`.");
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
            ${relativeTime ? `<span class="model-item-divider">•</span> <span class="model-item-modified">Modified ${relativeTime}</span>` : ''}
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
            res = await ApiClient.switchOllamaModel(model.name);
          } else if (activeProvider === "gemini") {
            res = await ApiClient.switchGeminiModel(model.name);
          } else if (activeProvider === "grok") {
            res = await ApiClient.switchGrokModel(model.name);
          }
          
          if (overlay) overlay.classList.remove("show");
          trigger.classList.remove("open");
          dropdown.classList.remove("visible");
          trigger.setAttribute("aria-expanded", "false");

          if (res && res.status === "ok") {
            if (activeProvider === "ollama") {
              activeOllamaModel = model.name;
              const sel = document.getElementById("setting-ollama-model");
              if (sel) sel.value = model.name;
              showToast(`Switched active Ollama model to <strong>${cleanModelName(model.name)}</strong>`);
            } else if (activeProvider === "gemini") {
              activeGeminiModel = model.name;
              const sel = document.getElementById("setting-gemini-model");
              if (sel) sel.value = model.name;
              showToast(`Switched active Gemini model to <strong>${cleanModelName(model.name)}</strong>`);
            } else if (activeProvider === "grok") {
              activeGrokModel = model.name;
              const sel = document.getElementById("setting-grok-model");
              if (sel) sel.value = model.name;
              showToast(`Switched active Grok model to <strong>${cleanModelName(model.name)}</strong>`);
            }
            loadSettings();
          } else {
            showToast("Failed to switch active model", true);
          }
        } catch (err) {
          console.error("Error switching model:", err);
          if (overlay) overlay.classList.remove("show");
          trigger.classList.remove("open");
          dropdown.classList.remove("visible");
          trigger.setAttribute("aria-expanded", "false");
          showToast("Network error switching active model", true);
        } finally {
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

  function showToast(message, isError = false) {
    const toast = document.getElementById("model-switch-toast");
    const toastMsg = document.getElementById("model-switch-toast-message");
    const toastIcon = toast?.querySelector(".toast-icon");
    if (!toast || !toastMsg) return;

    toastMsg.innerHTML = message;
    if (isError) {
      toast.style.borderColor = "var(--bad-border)";
      if (toastIcon) toastIcon.textContent = "❌";
    } else {
      toast.style.borderColor = "var(--good-border)";
      if (toastIcon) toastIcon.textContent = "✅";
    }

    toast.classList.add("show");
    setTimeout(() => {
      toast.classList.remove("show");
    }, 4000);
  }
}

