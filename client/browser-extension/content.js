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

// ---------- results panel — enterprise UI ----------

const STEP_LABELS = {
  1: "AI Insights", 2: "Content Analyser", 3: "Authenticity",
  4: "Actionable Items", 5: "Learnings",
};

const STEP_ICONS = { 1: "💡", 2: "🔬", 3: "✅", 4: "🎯", 5: "📚" };

let pipelineTimeoutSeconds = 120;
const activeTimers = {};

// ─── Inject scoped stylesheet (once) ───
function injectPanelStyles() {
  if (document.getElementById("usisain-panel-styles")) return;
  const style = document.createElement("style");
  style.id = "usisain-panel-styles";
  style.textContent = `
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    #usisain-panel {
      position: fixed; bottom: 20px; right: 20px; width: 380px; max-height: 75vh;
      overflow-y: auto; z-index: 999999;
      background: linear-gradient(170deg, rgba(12,14,22,0.97) 0%, rgba(18,22,34,0.98) 100%);
      color: #e8ecf4;
      border-radius: 16px;
      border: 1px solid rgba(56,68,102,0.35);
      box-shadow: 0 12px 48px rgba(0,0,0,0.6), 0 0 0 1px rgba(96,165,250,0.08);
      font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif;
      font-size: 13px; line-height: 1.5;
      backdrop-filter: blur(16px);
      animation: usisainSlideIn 0.35s cubic-bezier(0.16, 1, 0.3, 1);
    }

    @keyframes usisainSlideIn {
      from { opacity: 0; transform: translateY(20px) scale(0.97); }
      to   { opacity: 1; transform: translateY(0) scale(1); }
    }

    #usisain-panel::-webkit-scrollbar { width: 4px; }
    #usisain-panel::-webkit-scrollbar-track { background: transparent; }
    #usisain-panel::-webkit-scrollbar-thumb { background: rgba(56,68,102,0.4); border-radius: 4px; }
    #usisain-panel::-webkit-scrollbar-thumb:hover { background: rgba(96,165,250,0.4); }

    .usisain-header {
      position: relative; padding: 16px 18px 14px;
      background: linear-gradient(135deg, #0f1629 0%, #162040 50%, #0d1a2e 100%);
      border-bottom: 1px solid rgba(56,68,102,0.35);
      border-radius: 16px 16px 0 0; overflow: hidden;
    }

    .usisain-header::before {
      content: ''; position: absolute; top: -50%; left: -50%; width: 200%; height: 200%;
      background: radial-gradient(ellipse at 30% 50%, rgba(96,165,250,0.08) 0%, transparent 60%),
                  radial-gradient(ellipse at 70% 50%, rgba(45,212,191,0.06) 0%, transparent 60%);
      animation: usisainHeaderShimmer 8s ease-in-out infinite alternate;
      pointer-events: none;
    }

    @keyframes usisainHeaderShimmer {
      0%   { transform: translate(0, 0); }
      100% { transform: translate(5%, -3%); }
    }

    .usisain-header-inner {
      display: flex; align-items: center; gap: 10px; position: relative; z-index: 1;
    }

    .usisain-header-icon {
      width: 30px; height: 30px;
      background: linear-gradient(135deg, #60a5fa 0%, #818cf8 50%, #2dd4bf 100%);
      border-radius: 8px; display: flex; align-items: center; justify-content: center;
      font-size: 15px; flex-shrink: 0;
      box-shadow: 0 2px 10px rgba(96,165,250,0.25);
    }

    .usisain-header-text { flex: 1; }

    .usisain-header-title {
      font-size: 14px; font-weight: 700; letter-spacing: -0.3px;
      background: linear-gradient(135deg, #60a5fa 0%, #818cf8 50%, #2dd4bf 100%);
      -webkit-background-clip: text; -webkit-text-fill-color: transparent;
      background-clip: text;
    }

    .usisain-header-sub {
      font-size: 10px; color: #5a6478; text-transform: uppercase;
      letter-spacing: 1px; margin-top: 1px;
    }

    .usisain-close-btn {
      position: relative; z-index: 1; width: 26px; height: 26px; border: none;
      background: rgba(56,68,102,0.3); color: #8892a8; border-radius: 6px;
      cursor: pointer; display: flex; align-items: center; justify-content: center;
      font-size: 13px; transition: all 0.2s ease; flex-shrink: 0;
      font-family: 'Inter', system-ui, sans-serif;
    }
    .usisain-close-btn:hover { background: rgba(248,113,113,0.15); color: #f87171; }

    .usisain-steps-container { padding: 6px 14px 14px; }

    .usisain-step-row {
      padding: 12px 0; position: relative;
      border-bottom: 1px solid rgba(56,68,102,0.2);
      transition: all 0.3s ease;
    }
    .usisain-step-row:last-child { border-bottom: none; }

    .usisain-step-inner { display: flex; gap: 12px; align-items: flex-start; }

    .usisain-step-badge {
      width: 32px; height: 32px; border-radius: 10px; flex-shrink: 0;
      display: flex; align-items: center; justify-content: center;
      font-size: 14px; font-weight: 700;
      background: rgba(56,68,102,0.2); border: 1px solid rgba(56,68,102,0.3);
      color: #5a6478; transition: all 0.4s ease;
    }

    .usisain-step-row[data-status="in_progress"] .usisain-step-badge {
      background: rgba(96,165,250,0.12); border-color: rgba(96,165,250,0.3);
      color: #60a5fa; box-shadow: 0 0 12px rgba(96,165,250,0.15);
    }

    .usisain-step-row[data-status="completed"] .usisain-step-badge {
      background: rgba(52,211,153,0.12); border-color: rgba(52,211,153,0.3);
      color: #34d399; box-shadow: 0 0 12px rgba(52,211,153,0.15);
    }

    .usisain-step-row[data-status="error"] .usisain-step-badge {
      background: rgba(248,113,113,0.12); border-color: rgba(248,113,113,0.3);
      color: #f87171; box-shadow: 0 0 12px rgba(248,113,113,0.15);
    }

    .usisain-step-content { flex: 1; min-width: 0; }

    .usisain-step-label {
      font-size: 11px; font-weight: 600; text-transform: uppercase;
      letter-spacing: 0.6px; color: #8892a8; margin-bottom: 2px;
      display: flex; align-items: center; gap: 6px;
    }

    .usisain-step-num {
      font-size: 9px; font-weight: 700; color: #5a6478;
      background: rgba(56,68,102,0.25); padding: 1px 5px; border-radius: 4px;
    }

    .usisain-body {
      color: #8892a8; margin-top: 3px; font-size: 12.5px;
      line-height: 1.5; word-break: break-word;
      transition: color 0.3s ease;
    }

    .usisain-step-row[data-status="completed"] .usisain-body {
      color: #c8d0e0;
    }

    .usisain-step-row[data-status="error"] .usisain-body {
      color: #f87171;
    }

    .usisain-progress-track {
      height: 2px; background: rgba(56,68,102,0.2); border-radius: 2px;
      margin-top: 8px; overflow: hidden; display: none;
    }

    .usisain-step-row[data-status="in_progress"] .usisain-progress-track {
      display: block;
    }

    .usisain-progress-bar {
      height: 100%; width: 40%; border-radius: 2px;
      background: linear-gradient(90deg, #60a5fa, #818cf8, #2dd4bf);
      animation: usisainProgressSlide 1.5s ease-in-out infinite;
    }

    @keyframes usisainProgressSlide {
      0%   { transform: translateX(-100%); }
      100% { transform: translateX(350%); }
    }

    .usisain-body a {
      color: #60a5fa !important; text-decoration: underline !important;
      word-break: break-all;
    }

    .usisain-body strong { color: #e8ecf4; font-weight: 600; }

    #usisain-temp-banner {
      margin: 10px 14px 0; padding: 8px 12px; border-radius: 8px;
      background: rgba(96,165,250,0.08); border: 1px solid rgba(96,165,250,0.2);
      color: #60a5fa; font-size: 11px; font-weight: 500;
      font-family: 'Inter', system-ui, sans-serif;
      display: flex; align-items: center; gap: 8px;
      animation: usisainFadeIn 0.25s ease;
    }

    @keyframes usisainFadeIn {
      from { opacity: 0; transform: translateY(-4px); }
      to   { opacity: 1; transform: translateY(0); }
    }

    #usisain-error-banner {
      margin: 10px 14px 0; padding: 10px 14px; border-radius: 10px;
      background: rgba(248,113,113,0.08); border: 1px solid rgba(248,113,113,0.25);
      color: #f87171; font-size: 12px; font-family: 'Inter', monospace;
      white-space: pre-wrap; word-break: break-word; line-height: 1.5;
      animation: usisainFadeIn 0.25s ease;
    }
  `;
  document.head.appendChild(style);
}

function clearTimerForStep(step) {
  if (activeTimers[step]) {
    clearInterval(activeTimers[step]);
    delete activeTimers[step];
  }
}

// Temporary banner helpers
function showTemporaryBanner(text) {
  let banner = document.getElementById('usisain-temp-banner');
  if (!banner) {
    banner = document.createElement('div');
    banner.id = 'usisain-temp-banner';
  }
  banner.innerHTML = `<span style="animation: usisainProgressSlide 1.5s ease-in-out infinite; display:inline-block;">⏳</span> ${text}`;
  const panel = document.getElementById('usisain-panel');
  if (panel) {
    if (panel.querySelector('#usisain-temp-banner')) panel.querySelector('#usisain-temp-banner').remove();
    const stepsContainer = panel.querySelector('.usisain-steps-container');
    if (stepsContainer) {
      panel.insertBefore(banner, stepsContainer);
    } else {
      panel.appendChild(banner);
    }
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
  const badge = row.querySelector(".usisain-step-badge");
  const body = row.querySelector(".usisain-body");
  row.dataset.status = status;
  badge.textContent = iconText;
  body.innerHTML = bodyHtml;
}

function markRemainingStepsFailed(startStep) {
  for (let step = startStep; step <= 5; step++) {
    const row = document.getElementById(`usisain-step-${step}`);
    if (!row || (row.dataset.status !== "pending" && row.dataset.status !== "in_progress")) continue;
    clearTimerForStep(step);
    setPanelStepStatus(step, "error", "✕", formatContent("Skipped because a previous step failed."));
  }
}

function showPanel() {
  injectPanelStyles();
  document.getElementById("usisain-panel")?.remove();
  // Clear any active timers from a previous run
  for (let step = 1; step <= 5; step++) {
    clearTimerForStep(step);
  }

  const panel = document.createElement("div");
  panel.id = "usisain-panel";

  // ── Header ──
  const header = document.createElement("div");
  header.className = "usisain-header";
  header.innerHTML = `
    <div class="usisain-header-inner">
      <div class="usisain-header-icon">🛡️</div>
      <div class="usisain-header-text">
        <div class="usisain-header-title">UsisAIn</div>
        <div class="usisain-header-sub">5-Step Analysis Pipeline</div>
      </div>
      <button class="usisain-close-btn" title="Close panel">✕</button>
    </div>`;
  header.querySelector(".usisain-close-btn").onclick = () => {
    panel.style.animation = "none";
    panel.style.opacity = "0";
    panel.style.transform = "translateY(20px) scale(0.97)";
    panel.style.transition = "all 0.25s ease";
    setTimeout(() => panel.remove(), 250);
  };
  panel.appendChild(header);

  // ── Steps container ──
  const stepsContainer = document.createElement("div");
  stepsContainer.className = "usisain-steps-container";

  for (let step = 1; step <= 5; step++) {
    const row = document.createElement("div");
    row.id = `usisain-step-${step}`;
    row.className = "usisain-step-row";
    row.dataset.status = "pending";
    row.innerHTML = `
      <div class="usisain-step-inner">
        <div class="usisain-step-badge">${step}</div>
        <div class="usisain-step-content">
          <div class="usisain-step-label">
            <span class="usisain-step-num">STEP ${step}</span>
            ${STEP_LABELS[step]}
          </div>
          <div class="usisain-body">Waiting…</div>
          <div class="usisain-progress-track"><div class="usisain-progress-bar"></div></div>
        </div>
      </div>`;
    stepsContainer.appendChild(row);
  }

  panel.appendChild(stepsContainer);
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
    return `<a href="${url}" target="_blank">${linkText}</a>`;
  });

  escaped = escaped.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  return escaped.replace(/\n/g, "<br>");
}

function updatePanelStep(event) {
  const row = document.getElementById(`usisain-step-${event.step}`);
  if (!row) return;
  const badge = row.querySelector(".usisain-step-badge");
  const body = row.querySelector(".usisain-body");

  clearTimerForStep(event.step);

  if (event.status === "in_progress") {
    badge.textContent = STEP_ICONS[event.step] || "⏳";
    row.dataset.status = "in_progress";
    let secondsLeft = pipelineTimeoutSeconds;
    body.textContent = `Analyzing… ${secondsLeft}s remaining`;
    activeTimers[event.step] = setInterval(() => {
      secondsLeft--;
      if (secondsLeft <= 0) {
        clearTimerForStep(event.step);
        if (row.dataset.status === "in_progress") {
          badge.textContent = "✕";
          row.dataset.status = "error";
          body.innerHTML = formatContent(`Step timed out after ${pipelineTimeoutSeconds} seconds.`);
          markRemainingStepsFailed(event.step + 1);
        }
      } else {
        body.textContent = `Analyzing… ${secondsLeft}s remaining`;
      }
    }, 1000);
  } else if (event.status === "error") {
    badge.textContent = "✕";
    row.dataset.status = "error";
    body.innerHTML = formatContent(event.result?.error || "Something went wrong on this step.");
    markRemainingStepsFailed(event.step + 1);
  } else if (event.status === "completed") {
    badge.textContent = "✓";
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
  if (!panel) {
    // If no panel exists yet, create one to show the error
    showPanel();
    return showPanelError(error);
  }
  // Update the header subtitle
  const headerSub = panel.querySelector(".usisain-header-sub");
  if (headerSub) headerSub.textContent = "Error Encountered";
  // Insert (or update) an error banner
  let banner = document.getElementById("usisain-error-banner");
  if (!banner) {
    banner = document.createElement("div");
    banner.id = "usisain-error-banner";
    const stepsContainer = panel.querySelector('.usisain-steps-container');
    if (stepsContainer) {
      panel.insertBefore(banner, stepsContainer);
    } else {
      panel.appendChild(banner);
    }
  }
  banner.textContent = "⚠️ " + error;
}
