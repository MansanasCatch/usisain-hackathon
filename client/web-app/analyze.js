const STEP_LABELS = {
  1: "(Step 1) AI Insights", 2: "(Step 2) Content Analyser", 3: "(Step 3) Authenticity",
  4: "(Step 4) Actionable Items", 5: "(Step 5) Learnings",
};

const modeSelect = document.getElementById("content-mode");
const textInput = document.getElementById("text-input");
const fileInput = document.getElementById("file-input");
const providerSelect = document.getElementById("llm-provider");
const form = document.getElementById("analyze-form");
const submitBtn = document.getElementById("submit-btn");
const resultsPanel = document.getElementById("results");
const resultsHeader = document.getElementById("results-header");

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

async function loadSettings() {
  try {
    const response = await fetch("/api/settings");
    if (!response.ok) return;
    const settings = await response.json();
    if (settings?.pipeline_step_timeout_seconds) {
      pipelineTimeoutSeconds = Number(settings.pipeline_step_timeout_seconds) || pipelineTimeoutSeconds;
    }
    if (settings?.default_llm_provider) {
      providerSelect.value = settings.default_llm_provider;
    }
  } catch (err) {
    console.warn("Unable to load settings:", err);
  }
}

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
  } else if (event.status === "completed") {
    icon.textContent = "✅";
    icon.style.color = "";
    row.style.color = "";
    body.style.color = "";
    row.dataset.status = "completed";
    body.innerHTML = formatContent(summarizeStep(event.step, event.result));
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
  const provider = providerSelect.value || "ollama";
  const formData = new FormData();
  formData.append("language", language);
  formData.append("provider", provider);
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
