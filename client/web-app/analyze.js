const STEP_LABELS = {
  1: "AI Insights", 2: "Content Analyser", 3: "Authenticity",
  4: "Actionable Items", 5: "Learnings",
};

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

// ─── Provider-aware language map (updated from /api/settings if available) ───
let supportedLanguages = {
  ollama: ["english"],
  gemini: ["english", "taglish", "tagalog", "cebuano", "bisaya", "ilocano"],
  grok: ["english", "taglish", "tagalog", "cebuano", "bisaya", "ilocano"],
};

const modeSelect = document.getElementById("content-mode");
const textInput = document.getElementById("text-input");
const fileInput = document.getElementById("file-input");
const providerSelect = document.getElementById("llm-provider");
const languageSelect = document.getElementById("language");
const form = document.getElementById("analyze-form");
const submitBtn = document.getElementById("submit-btn");
const resultsPanel = document.getElementById("results");
const resultsHeader = document.getElementById("results-header");

// ─── Filter languages based on selected provider ───
function updateLanguageOptions() {
  const provider = providerSelect.value || "ollama";
  const allowed = supportedLanguages[provider] || supportedLanguages.ollama || ["english"];
  const currentValue = languageSelect.value;

  languageSelect.innerHTML = "";
  for (const lang of allowed) {
    const option = document.createElement("option");
    option.value = lang;
    option.textContent = lang.charAt(0).toUpperCase() + lang.slice(1);
    languageSelect.appendChild(option);
  }

  // Restore selection if still valid, otherwise default to english
  if (allowed.includes(currentValue)) {
    languageSelect.value = currentValue;
  } else {
    languageSelect.value = "english";
  }
}

providerSelect.addEventListener("change", updateLanguageOptions);

function updateFormFields() {
  const mode = modeSelect.value;
  textInput.style.display = (mode === "text" || mode === "post") ? "block" : "none";
  fileInput.style.display = (mode === "image" || mode === "video" || mode === "post") ? "block" : "none";
  fileInput.accept = mode === "video" ? "video/*" : "image/*";
  textInput.placeholder = mode === "post"
    ? "Paste the post's caption..."
    : "Paste the claim or message to check...";
}
modeSelect.addEventListener("change", updateFormFields);
updateFormFields();

let pipelineTimeoutSeconds = 120;
const activeTimers = {};
const spokenStarts = {};
const spokenCompletes = {};

async function loadSettings() {
  try {
    const response = await fetch("/api/settings");
    if (!response.ok) return;
    const settings = await response.json();
    if (settings?.pipeline_step_timeout_seconds) {
      pipelineTimeoutSeconds = Number(settings.pipeline_step_timeout_seconds) || pipelineTimeoutSeconds;
    }
    // Use server-provided language map if available
    if (settings?.supported_languages) {
      supportedLanguages = settings.supported_languages;
    }
    if (settings?.default_llm_provider) {
      providerSelect.value = settings.default_llm_provider;
    }
    if (settings?.tts_enabled !== undefined) {
      document.getElementById("tts-toggle").checked = settings.tts_enabled;
      window.ttsPlayer.setEnabled(settings.tts_enabled);
    }
    // Update language dropdown based on loaded provider
    updateLanguageOptions();
  } catch (err) {
    console.warn("Unable to load settings:", err);
  }
}

const ttsVoiceSelect = document.getElementById("tts-voice");
const ttsReplayBtn = document.getElementById("tts-replay");

function updateVoiceDropdownVisibility() {
  const ttsEnabled = document.getElementById("tts-toggle").checked;
  ttsVoiceSelect.style.display = ttsEnabled ? "inline-block" : "none";
  
  // Show replay button if TTS is enabled and there is completed text to replay
  const hasCompletedStep = Array.from(document.querySelectorAll(".step-row"))
    .some(row => row.dataset.status === "completed" && row.dataset.speechText);
  ttsReplayBtn.style.display = (ttsEnabled && hasCompletedStep) ? "inline-block" : "none";
}

function populateVoices() {
  ttsVoiceSelect.innerHTML = "";
  const voices = window.ttsPlayer.getVoices();
  for (const voice of voices) {
    const opt = document.createElement("option");
    opt.value = voice.name;
    opt.textContent = `${voice.name} (${voice.lang})`;
    ttsVoiceSelect.appendChild(opt);
  }
  if (window.ttsPlayer.selectedVoiceName) {
    ttsVoiceSelect.value = window.ttsPlayer.selectedVoiceName;
  }
}

document.getElementById("tts-toggle").addEventListener("change", (e) => {
  window.ttsPlayer.setEnabled(e.target.checked);
  updateVoiceDropdownVisibility();
});

ttsVoiceSelect.addEventListener("change", (e) => {
  window.ttsPlayer.setSelectedVoice(e.target.value);
});

ttsReplayBtn.addEventListener("click", () => {
  window.ttsPlayer.stop();
  for (let i = 1; i <= 5; i++) {
    delete spokenCompletes[i];
  }
  
  // Enqueue all already-completed steps in order
  for (let i = 1; i <= 5; i++) {
    const row = document.getElementById(`step-${i}`);
    if (row && row.dataset.status === "completed" && row.dataset.speechText) {
      spokenCompletes[i] = true;
      window.ttsPlayer.speak(row.dataset.speechText);
    }
  }
});

if (window.ttsPlayer) {
  window.ttsPlayer.initVoices();
}
populateVoices();
updateVoiceDropdownVisibility();

loadSettings();

function clearTimerForStep(step) {
  if (activeTimers[step]) {
    clearInterval(activeTimers[step]);
    delete activeTimers[step];
  }
}

function setStepRowStatus(step, status, iconText, bodyHtml, color) {
  const row = document.getElementById(`step-${step}`);
  if (!row) return;
  const icon = row.querySelector(".step-icon");
  const body = row.querySelector(".step-body");
  row.dataset.status = status;
  icon.textContent = iconText;
  if (color) {
    icon.style.color = color;
    row.style.color = color;
    body.style.color = color;
  } else {
    icon.style.color = "";
    row.style.color = "";
    body.style.color = "";
  }
  body.innerHTML = bodyHtml;
}

function markFollowingStepsFailed(startStep) {
  for (let step = startStep; step <= 5; step++) {
    const row = document.getElementById(`step-${step}`);
    if (!row || (row.dataset.status !== "pending" && row.dataset.status !== "in_progress")) continue;
    clearTimerForStep(step);
    setStepRowStatus(step, "error", "⚠️", formatContent("Skipped because a previous step failed."), "var(--bad)");
  }
}

function initStepRows() {
  resultsPanel.style.display = "block";
  resultsHeader.textContent = "Analyzing…";
  // Remove any previous error banner
  document.getElementById("error-banner")?.remove();
  for (let step = 1; step <= 5; step++) {
    clearTimerForStep(step);
    const row = document.getElementById(`step-${step}`);
    row.dataset.status = "pending";
    row.style.cssText = `padding:10px 0; border-top:${step > 1 ? "1px solid var(--border)" : "none"};`;
    row.innerHTML = `<div style="display:flex; gap:10px; align-items:flex-start;">
      <span class="step-icon" style="flex-shrink:0;">⏳</span>
      <div style="flex:1;">
        <div style="font-weight:500;">${STEP_LABELS[step]}</div>
        <div class="step-body" style="color:var(--muted); margin-top:2px; font-size:13px; white-space:pre-wrap;">Waiting…</div>
      </div></div>`;
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
    return `<a href="${url}" target="_blank" style="color:#58a6ff; text-decoration:underline; word-break:break-all;">${linkText}</a>`;
  });

  escaped = escaped.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  return escaped.replace(/\n/g, "<br>");
}

function updateStepRow(event) {
  const row = document.getElementById(`step-${event.step}`);
  if (!row) return;
  const icon = row.querySelector(".step-icon");
  const body = row.querySelector(".step-body");

  clearTimerForStep(event.step);

  if (event.status === "in_progress") {
    icon.textContent = "🔄";
    icon.style.color = "#58a6ff";
    row.style.color = "";
    body.style.color = "var(--muted)";
    row.dataset.status = "in_progress";
    let secondsLeft = pipelineTimeoutSeconds;
    body.textContent = `Working… (${secondsLeft}s remaining)`;
    
    // Narrate step start (ensure we only narrate it once)
    if (!spokenStarts[event.step]) {
      spokenStarts[event.step] = true;
      const lang = document.getElementById("language").value;
      const startMsgs = STEP_START_MESSAGES[lang] || STEP_START_MESSAGES.english;
      const startMsg = startMsgs[event.step] || `Starting step ${event.step}`;
      window.ttsPlayer.speak(startMsg);
    }

    activeTimers[event.step] = setInterval(() => {
      secondsLeft--;
      if (secondsLeft <= 0) {
        clearTimerForStep(event.step);
        if (row.dataset.status === "in_progress") {
          setStepRowStatus(event.step, "error", "⚠️", formatContent(`Step timed out after ${pipelineTimeoutSeconds} seconds.`), "var(--bad)");
          markFollowingStepsFailed(event.step + 1);
        }
      } else {
        body.textContent = `Working… (${secondsLeft}s remaining)`;
      }
    }, 1000);
  } else if (event.status === "error") {
    icon.textContent = "⚠️";
    icon.style.color = "var(--bad)";
    row.style.color = "var(--bad)";
    body.style.color = "var(--bad)";
    row.dataset.status = "error";
    body.innerHTML = formatContent(event.result?.error || "Something went wrong on this step.");
    markFollowingStepsFailed(event.step + 1);

    // Narrate step failure
    if (!spokenCompletes[event.step]) {
      spokenCompletes[event.step] = true;
      window.ttsPlayer.speak(`Step ${event.step} failed. ${event.result?.error || ""}`);
    }
  } else if (event.status === "completed") {
    icon.textContent = "✅";
    icon.style.color = "";
    row.style.color = "";
    body.style.color = "";
    row.dataset.status = "completed";
    body.innerHTML = formatContent(summarizeStep(event.step, event.result));

    // Narrate step output
    const lang = document.getElementById("language").value;
    window.ttsPlayer.setLanguage(lang);
    let speechText = summarizeStep(event.step, event.result);
    if (event.step === 2 && event.result.applicable !== false) {
      speechText = `Visual analysis breakdown: ${event.result.real_pct}% real, ${event.result.edited_pct}% edited, and ${event.result.ai_generated_pct}% AI-generated. ${event.result.explanation}`;
    } else if (event.step === 3) {
      speechText = `Verdict: ${event.result.verdict}. Credibility score: ${event.result.score} out of 100. ${event.result.explanation}`;
    } else if (event.step === 4) {
      speechText = `Here are the actionable items: ${(event.result.actions || []).join(". ")}`;
    }
    
    // Store speech text representation on the element for replay
    row.dataset.speechText = speechText;
    updateVoiceDropdownVisibility();

    if (!spokenCompletes[event.step]) {
      spokenCompletes[event.step] = true;
      window.ttsPlayer.speak(speechText);
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


form.addEventListener("submit", async (e) => {
  e.preventDefault();
  submitBtn.disabled = true;
  initStepRows();

  const mode = modeSelect.value;
  const language = document.getElementById("language").value;
  
  // Clear step spoken states on new submit session
  for (let i = 1; i <= 5; i++) {
    delete spokenStarts[i];
    delete spokenCompletes[i];
    const row = document.getElementById(`step-${i}`);
    if (row) delete row.dataset.speechText;
  }
  updateVoiceDropdownVisibility();

  // Set language and stop previous speech
  window.ttsPlayer.setLanguage(language);
  window.ttsPlayer.stop();

  const provider = providerSelect.value || "ollama";
  const useOcr = document.getElementById("ocr-toggle") ? document.getElementById("ocr-toggle").checked : true;
  const formData = new FormData();
  formData.append("language", language);
  formData.append("provider", provider);
  formData.append("use_ocr", useOcr.toString());
  formData.append("source_url", location.href);

  if (mode === "text") {
    formData.append("text", textInput.value);
  } else if (mode === "image" || mode === "video") {
    if (!fileInput.files[0]) { submitBtn.disabled = false; return; }
    const file = fileInput.files[0];
    if (file.type && file.type.startsWith("image/")) {
      try {
        const resized = await resizeImageFile(file, 1024, 0.75);
        formData.append("file", resized, file.name);
      } catch (err) {
        // If resizing fails for any reason, fall back to the original file
        formData.append("file", file);
      }
    } else {
      // video or unknown — send as-is
      formData.append("file", file);
    }
  } else if (mode === "post") {
    formData.append("caption", textInput.value);
    if (fileInput.files[0]) {
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
    }
  }



// Resize an image File in the browser using a canvas and return a Blob.
// Keeps images under `maxDim` px on the longest side and compresses to JPEG.
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
  try {
    await streamAnalyze(formData, (event) => {
      if (event.done) {
        resultsHeader.textContent = `Done — scan #${event.scan_id}`;
        return;
      }
      if (event.systemError) {
        // Top-level error (e.g. Gemini quota exceeded, server crash)
        resultsHeader.textContent = "Error";
        let errDiv = document.getElementById("error-banner");
        if (!errDiv) {
          errDiv = document.createElement("div");
          errDiv.id = "error-banner";
          errDiv.style.cssText = "background:rgba(230,88,79,0.15); border:1px solid var(--bad); border-radius:8px; padding:12px; margin-bottom:12px; color:var(--bad); font-size:13px; font-family:monospace; white-space:pre-wrap;";
          resultsPanel.insertBefore(errDiv, resultsPanel.children[1]);
        }
        errDiv.textContent = "⚠️ " + event.systemError;
        return;
      }
      updateStepRow(event);
    });
  } catch (err) {
    resultsHeader.textContent = `Error: ${err.message}`;
  } finally {
    submitBtn.disabled = false;
  }
});
