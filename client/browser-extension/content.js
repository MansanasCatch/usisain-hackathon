// content.js — runs in the page. Handles two jobs:
//   1. Tracking the right-clicked element and extracting page/post context.
//   2. Rendering the progressive 5-step results panel as events stream in
//      from background.js (which does the actual fetch to the backend).

let lastRightClickedEl = null;
document.addEventListener("contextmenu", (e) => { lastRightClickedEl = e.target; }, true);

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  // Ping/pong — lets the background script know we're already injected
  if (message.action === "ping") {
    sendResponse({ pong: true });
    return;
  }

  if (message.action === "get-context") {
    const el = lastRightClickedEl;
    const post = getPostContext(el);
    sendResponse({
      pageUrl: location.href,
      selectedText: window.getSelection()?.toString() || null,
      clickedImageSrc: message.srcUrl || (el && el.tagName === "IMG" ? el.src : null),
      clickedVideoSrc: message.srcUrl || (el && el.tagName === "VIDEO" ? el.currentSrc : null),
      postCaption: post.caption,
      postImages: post.images,
    });
    return true;
  }

  if (message.action === "fetch-as-dataurl") {
    fetch(message.url).then(res => res.blob()).then(blob => new Promise((resolve) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result);
      reader.readAsDataURL(blob);
    })).then(dataUrl => sendResponse({ dataUrl })).catch(err => sendResponse({ error: String(err) }));
    return true;
  }
  
  if (message.action === "fetch-and-resize") {
    // message: { action: 'fetch-and-resize', url, maxDim, quality }
    const { url, maxDim = 1024, quality = 0.75 } = message;
    (async () => {
      try {
        showTemporaryBanner('Resizing image...');
        const resp = await fetch(url);
        const blob = await resp.blob();
        const dataUrl = await resizeBlobToDataUrl(blob, maxDim, quality);
        clearTemporaryBanner();
        sendResponse({ dataUrl });
      } catch (err) {
        clearTemporaryBanner();
        sendResponse({ error: String(err) });
      }
    })();
    return true;
  }

  if (message.action === 'upload-start') {
    showTemporaryBanner('Uploading…');
    sendResponse({ ok: true });
    return true;
  }

  if (message.action === 'upload-end') {
    clearTemporaryBanner();
    sendResponse({ ok: true });
    return true;
  }

  if (message.action === "pipeline-start") { showPanel(); return; }
  if (message.action === "pipeline-settings") {
    pipelineTimeoutSeconds = Number(message.pipeline_step_timeout_seconds) || pipelineTimeoutSeconds;
    return;
  }
  if (message.action === "pipeline-event") { updatePanelStep(message.event); return; }
  if (message.action === "pipeline-error") { showPanelError(message.error); return; }
});

// ---------- results panel ----------

const STEP_LABELS = {
  1: "(Step 1) AI Insights", 2: "(Step 2) Content Analyser", 3: "(Step 3) Authenticity",
  4: "(Step 4) Actionable Items", 5: "(Step 5) Learnings",
};

let pipelineTimeoutSeconds = 120;
const activeTimers = {};

function clearTimerForStep(step) {
  if (activeTimers[step]) {
    clearInterval(activeTimers[step]);
    delete activeTimers[step];
  }
}

// Temporary banner helpers (small lightweight progress indicator)
function showTemporaryBanner(text) {
  let banner = document.getElementById('usisain-temp-banner');
  if (!banner) {
    banner = document.createElement('div');
    banner.id = 'usisain-temp-banner';
    Object.assign(banner.style, {
      background: '#0b1220', color: '#dbe9ff', padding: '8px 10px', borderRadius: '8px',
      fontSize: '12px', fontFamily: 'system-ui, sans-serif', marginBottom: '8px'
    });
  }
  banner.textContent = text;
  const panel = document.getElementById('usisain-panel');
  if (panel) {
    if (panel.querySelector('#usisain-temp-banner')) panel.querySelector('#usisain-temp-banner').remove();
    panel.insertBefore(banner, panel.firstChild?.nextSibling || panel.firstChild);
  }
}

function clearTemporaryBanner() {
  document.getElementById('usisain-temp-banner')?.remove();
}

async function resizeBlobToDataUrl(blob, maxDim = 1024, quality = 0.75) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const url = URL.createObjectURL(blob);
    img.onload = () => {
      try {
        let { width, height } = img;
        const maxSide = Math.max(width, height);
        let scale = 1;
        if (maxSide > maxDim) scale = maxDim / maxSide;
        if (scale >= 1) {
          URL.revokeObjectURL(url);
          // return original blob as dataURL
          const reader = new FileReader();
          reader.onloadend = () => resolve(reader.result);
          reader.readAsDataURL(blob);
          return;
        }

        const canvas = document.createElement('canvas');
        canvas.width = Math.round(width * scale);
        canvas.height = Math.round(height * scale);
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        const dataUrl = canvas.toDataURL('image/jpeg', quality);
        URL.revokeObjectURL(url);
        resolve(dataUrl);
      } catch (err) {
        URL.revokeObjectURL(url);
        reject(err);
      }
    };
    img.onerror = (e) => { URL.revokeObjectURL(url); reject(e || new Error('Image load error')); };
    img.src = url;
  });
}

function setPanelStepStatus(step, status, iconText, bodyHtml, color) {
  const row = document.getElementById(`usisain-step-${step}`);
  if (!row) return;
  const icon = row.querySelector(".usisain-icon");
  const body = row.querySelector(".usisain-body");
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

function markRemainingStepsFailed(startStep) {
  for (let step = startStep; step <= 5; step++) {
    const row = document.getElementById(`usisain-step-${step}`);
    if (!row || (row.dataset.status !== "pending" && row.dataset.status !== "in_progress")) continue;
    clearTimerForStep(step);
    setPanelStepStatus(step, "error", "⚠️", formatContent("Skipped because a previous step failed."), "#ff7b72");
  }
}

function showPanel() {
  document.getElementById("usisain-panel")?.remove();
  // Clear any active timers from a previous run
  for (let step = 1; step <= 5; step++) {
    clearTimerForStep(step);
  }
  const panel = document.createElement("div");
  panel.id = "usisain-panel";
  Object.assign(panel.style, {
    position: "fixed", bottom: "20px", right: "20px", width: "340px", maxHeight: "70vh",
    overflowY: "auto", zIndex: 999999, background: "#171a21", color: "#e7e9ee",
    borderRadius: "12px", boxShadow: "0 8px 30px rgba(0,0,0,0.5)", fontFamily: "system-ui, sans-serif",
    fontSize: "13px", padding: "12px",
  });

  const header = document.createElement("div");
  header.textContent = "UsisAIn — 5 Steps Pipeline";
  Object.assign(header.style, { fontWeight: "600", marginBottom: "8px", display: "flex", justifyContent: "space-between" });
  const closeBtn = document.createElement("span");
  closeBtn.textContent = "✕";
  closeBtn.style.cursor = "pointer";
  closeBtn.onclick = () => panel.remove();
  header.appendChild(closeBtn);
  panel.appendChild(header);

  for (let step = 1; step <= 5; step++) {
    const row = document.createElement("div");
    row.id = `usisain-step-${step}`;
    row.dataset.status = "pending";
    Object.assign(row.style, { padding: "8px 0", borderTop: step > 1 ? "1px solid #2a2e38" : "none" });
    row.innerHTML = `<div style="display:flex; gap:8px; align-items:flex-start;">
      <span class="usisain-icon" style="flex-shrink:0;">⏳</span>
      <div style="flex:1;">
        <div style="font-weight:500;">${STEP_LABELS[step]}</div>
        <div class="usisain-body" style="color:#9aa1ac; margin-top:2px;">Waiting…</div>
      </div></div>`;
    panel.appendChild(row);
  }

  document.body.appendChild(panel);
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

function updatePanelStep(event) {
  const row = document.getElementById(`usisain-step-${event.step}`);
  if (!row) return;
  const icon = row.querySelector(".usisain-icon");
  const body = row.querySelector(".usisain-body");

  clearTimerForStep(event.step);

  if (event.status === "in_progress") {
    icon.textContent = "🔄";
    icon.style.color = "#58a6ff";
    row.style.color = "";
    body.style.color = "#9aa1ac";
    row.dataset.status = "in_progress";
    let secondsLeft = pipelineTimeoutSeconds;
    body.textContent = `Working… (${secondsLeft}s remaining)`;
    activeTimers[event.step] = setInterval(() => {
      secondsLeft--;
      if (secondsLeft <= 0) {
        clearTimerForStep(event.step);
        if (row.dataset.status === "in_progress") {
          icon.textContent = "⚠️";
          icon.style.color = "#ff7b72";
          row.style.color = "#ff7b72";
          body.style.color = "#ff7b72";
          row.dataset.status = "error";
          body.innerHTML = formatContent(`Step timed out after ${pipelineTimeoutSeconds} seconds.`);
          markRemainingStepsFailed(event.step + 1);
        }
      } else {
        body.textContent = `Working… (${secondsLeft}s remaining)`;
      }
    }, 1000);
  } else if (event.status === "error") {
    icon.textContent = "⚠️";
    icon.style.color = "#ff7b72";
    row.style.color = "#ff7b72";
    body.style.color = "#ff7b72";
    row.dataset.status = "error";
    body.innerHTML = formatContent(event.result?.error || "Something went wrong on this step.");
    markRemainingStepsFailed(event.step + 1);
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
  if (step === 5) return result.learning_material || "No learnings generated.";
  return "Done.";
}


function showPanelError(error) {
  const panel = document.getElementById("usisain-panel");
  if (!panel) return;
  // Update the header
  const header = panel.querySelector("div");
  if (header) header.childNodes[0].textContent = "UsisAIn — Error";
  // Insert (or update) an error banner at the top
  let banner = document.getElementById("usisain-error-banner");
  if (!banner) {
    banner = document.createElement("div");
    banner.id = "usisain-error-banner";
    Object.assign(banner.style, {
      background: "rgba(230,88,79,0.15)", border: "1px solid #e6584f",
      borderRadius: "8px", padding: "10px", marginBottom: "8px",
      color: "#e6584f", fontSize: "12px", fontFamily: "monospace",
      whiteSpace: "pre-wrap", wordBreak: "break-word",
    });
    // Insert right after the header
    if (header.nextSibling) panel.insertBefore(banner, header.nextSibling);
    else panel.appendChild(banner);
  }
  banner.textContent = "⚠️ " + error;
}
