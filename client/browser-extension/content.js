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

  if (message.action === "start-snipping") {
    initializeSnippingTool(sendResponse);
    return true;
  }
  
  if (message.action === "crop-screenshot") {
    cropScreenshot(message.dataUrl, message.cropRect).then(croppedUrl => {
      sendResponse({ croppedDataUrl: croppedUrl });
    });
    return true;
  }

  if (message.action === "restore-scroll") {
    window.scrollTo(message.scrollX, message.scrollY);
    sendResponse({ ok: true });
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

    if (message.action === "pipeline-start") {
      ttsPlayer.stop();
      showPanel(message.previewText, message.previewImageUrl);
      return;
    }
    if (message.action === "pipeline-settings") {
      pipelineTimeoutSeconds = Number(message.pipeline_step_timeout_seconds) || pipelineTimeoutSeconds;
      if (message.tts_enabled !== undefined) {
        ttsPlayer.setEnabled(message.tts_enabled);
      }
      if (message.language) {
        ttsPlayer.setLanguage(message.language);
      }
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

    #usisain-panel, #usisain-panel * {
      box-sizing: border-box !important;
    }

    #usisain-panel {
      position: fixed; top: 0; right: 0; bottom: 0; width: 380px; height: 100vh;
      overflow-y: hidden; z-index: 999999;
      display: flex; flex-direction: column;
      background: linear-gradient(170deg, rgba(12,14,22,0.97) 0%, rgba(18,22,34,0.98) 100%);
      color: #e8ecf4;
      border-radius: 16px 0 0 16px;
      border: 1px solid rgba(56,68,102,0.35);
      border-right: none;
      box-shadow: -8px 0 48px rgba(0,0,0,0.5), 0 0 0 1px rgba(96,165,250,0.08);
      font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif;
      font-size: 13px; line-height: 1.5;
      backdrop-filter: blur(16px);
      animation: usisainSlideIn 0.35s cubic-bezier(0.16, 1, 0.3, 1);
      transition: height 0.35s cubic-bezier(0.16, 1, 0.3, 1),
                  top 0.35s cubic-bezier(0.16, 1, 0.3, 1),
                  left 0.35s cubic-bezier(0.16, 1, 0.3, 1),
                  border-radius 0.35s cubic-bezier(0.16, 1, 0.3, 1),
                  box-shadow 0.35s ease;
    }

    @keyframes usisainSlideIn {
      from { opacity: 0; transform: translateX(100%); }
      to   { opacity: 1; transform: translateX(0); }
    }

    .usisain-steps-container::-webkit-scrollbar { width: 4px; }
    .usisain-steps-container::-webkit-scrollbar-track { background: transparent; }
    .usisain-steps-container::-webkit-scrollbar-thumb { background: rgba(56,68,102,0.4); border-radius: 4px; }
    .usisain-steps-container::-webkit-scrollbar-thumb:hover { background: rgba(96,165,250,0.4); }

    .usisain-header {
      position: relative; padding: 16px 18px 14px;
      background: linear-gradient(135deg, #0f1629 0%, #162040 50%, #0d1a2e 100%);
      border-bottom: 1px solid rgba(56,68,102,0.35);
      border-radius: 16px 0 0 0; overflow: hidden;
      flex-shrink: 0 !important;
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

    .usisain-steps-container { padding: 6px 14px 14px; flex: 1; overflow-y: auto; }

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

    .usisain-header {
      cursor: move;
    }

    .usisain-close-btn, .usisain-minimize-btn {
      cursor: pointer !important;
    }

    .usisain-minimize-btn {
      position: relative; z-index: 1; width: 26px; height: 26px; border: none;
      background: rgba(56,68,102,0.3); color: #8892a8; border-radius: 6px;
      cursor: pointer; display: flex; align-items: center; justify-content: center;
      font-size: 13px; transition: all 0.2s ease; flex-shrink: 0;
      font-family: 'Inter', system-ui, sans-serif;
    }
    .usisain-minimize-btn:hover { background: rgba(96,165,250,0.15); color: #60a5fa; }

    #usisain-panel.usisain-minimized {
      height: 64px !important;
      bottom: auto !important;
      border-radius: 16px !important;
      border: 1px solid rgba(56, 68, 102, 0.35) !important;
      box-shadow: 0 8px 32px rgba(0,0,0,0.5);
    }
    #usisain-panel.usisain-minimized .usisain-header {
      border-bottom: none !important;
      border-radius: 15px !important;
      padding: 16px 18px !important;
    }
    #usisain-panel.usisain-minimized .usisain-preview-box,
    #usisain-panel.usisain-minimized .usisain-steps-container,
    #usisain-panel.usisain-minimized #usisain-error-banner,
    #usisain-panel.usisain-minimized #usisain-temp-banner {
      opacity: 0 !important;
      pointer-events: none !important;
      visibility: hidden !important;
      height: 0 !important;
      margin: 0 !important;
      padding: 0 !important;
      border: none !important;
      overflow: hidden !important;
      flex: 0 0 0 !important;
    }

    .usisain-preview-box,
    .usisain-steps-container,
    #usisain-error-banner,
    #usisain-temp-banner {
      transition: opacity 0.25s cubic-bezier(0.16, 1, 0.3, 1),
                  visibility 0.25s ease,
                  height 0.25s ease,
                  margin 0.25s ease,
                  padding 0.25s ease,
                  border-color 0.25s ease;
    }

    .usisain-preview-box {
      margin: 12px 14px 4px;
      padding: 10px;
      background: rgba(30, 41, 59, 0.5);
      border: 1px solid rgba(56, 68, 102, 0.3);
      border-radius: 12px;
      display: flex;
      flex-direction: column;
      gap: 8px;
      max-height: 180px;
      overflow: hidden;
    }

    .usisain-preview-img {
      width: 100%;
      max-height: 120px;
      object-fit: contain;
      border-radius: 8px;
      border: 1px solid rgba(255, 255, 255, 0.1);
      background: #090d16;
    }

    .usisain-preview-text {
      font-size: 12px;
      color: #cbd5e1;
      overflow-y: auto;
      max-height: 140px;
      white-space: pre-wrap;
      word-break: break-word;
      font-style: italic;
      padding-right: 4px;
    }

    .usisain-preview-text::-webkit-scrollbar { width: 4px; }
    .usisain-preview-text::-webkit-scrollbar-track { background: transparent; }
    .usisain-preview-text::-webkit-scrollbar-thumb { background: rgba(56,68,102,0.4); border-radius: 4px; }

    .usisain-preview-caption {
      font-size: 11px;
      color: #94a3b8;
      white-space: pre-wrap;
      word-break: break-word;
      font-style: italic;
      text-align: left;
      max-height: 60px;
      overflow-y: auto;
      padding-right: 4px;
    }
    .usisain-preview-caption::-webkit-scrollbar { width: 3px; }
    .usisain-preview-caption::-webkit-scrollbar-track { background: transparent; }
    .usisain-preview-caption::-webkit-scrollbar-thumb { background: rgba(56,68,102,0.4); border-radius: 2px; }
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

function showPanel(previewText, previewImageUrl) {
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
      <button class="usisain-minimize-btn" title="Minimize panel" style="margin-right: 8px;">🗕</button>
      <button class="usisain-close-btn" title="Close panel">✕</button>
    </div>`;
  header.querySelector(".usisain-close-btn").onclick = () => {
    panel.style.animation = "none";
    panel.style.opacity = "0";
    panel.style.transform = "translateX(100%)";
    panel.style.transition = "all 0.25s ease";
    setTimeout(() => panel.remove(), 250);
    chrome.runtime.sendMessage({ action: "cancel-analysis" });
  };
  header.querySelector(".usisain-minimize-btn").onclick = () => {
    const isMinimized = panel.classList.toggle("usisain-minimized");
    header.querySelector(".usisain-minimize-btn").textContent = isMinimized ? "🗖" : "🗕";
    header.querySelector(".usisain-minimize-btn").title = isMinimized ? "Maximize panel" : "Minimize panel";
    
    if (isMinimized) {
      panel.dataset.prevHeight = panel.style.height || "100vh";
      panel.style.height = "";
    } else {
      panel.style.height = panel.dataset.prevHeight || "100vh";
      const rect = panel.getBoundingClientRect();
      if (rect.top + rect.height > window.innerHeight) {
        panel.style.top = Math.max(0, window.innerHeight - rect.height) + "px";
      }
    }
  };
  panel.appendChild(header);

  // Dragging logic on header
  let isDragging = false;
  let startX = 0;
  let startY = 0;
  let initialLeft = 0;
  let initialTop = 0;

  header.addEventListener("mousedown", (e) => {
    if (e.target.closest("button")) return;

    isDragging = true;
    const rect = panel.getBoundingClientRect();
    
    panel.style.left = rect.left + "px";
    panel.style.top = rect.top + "px";
    panel.style.right = "auto";
    panel.style.bottom = "auto";
    panel.style.height = rect.height + "px";
    panel.style.transition = "none";

    startX = e.clientX;
    startY = e.clientY;
    initialLeft = rect.left;
    initialTop = rect.top;

    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
    
    e.preventDefault();
  });

  function onMouseMove(e) {
    if (!isDragging) return;
    const dx = e.clientX - startX;
    const dy = e.clientY - startY;
    
    let newLeft = initialLeft + dx;
    let newTop = initialTop + dy;

    const panelWidth = panel.offsetWidth;
    const panelHeight = panel.offsetHeight;
    newLeft = Math.max(0, Math.min(newLeft, window.innerWidth - panelWidth));
    newTop = Math.max(0, Math.min(newTop, window.innerHeight - panelHeight));

    panel.style.left = newLeft + "px";
    panel.style.top = newTop + "px";
  }

  function onMouseUp() {
    if (isDragging) {
      isDragging = false;
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
      panel.style.transition = "";
    }
  }

  // ── Preview container ──
  if (previewImageUrl) {
    const previewContainer = document.createElement("div");
    previewContainer.className = "usisain-preview-box";
    const img = document.createElement("img");
    img.src = previewImageUrl;
    img.className = "usisain-preview-img";
    previewContainer.appendChild(img);
    
    panel.appendChild(previewContainer);
  } else if (previewText) {
    const previewContainer = document.createElement("div");
    previewContainer.className = "usisain-preview-box";
    const textDiv = document.createElement("div");
    textDiv.className = "usisain-preview-text";
    textDiv.textContent = previewText;
    previewContainer.appendChild(textDiv);
    panel.appendChild(previewContainer);
  }

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

    // Narrate step start
    const startMsgs = STEP_START_MESSAGES[ttsPlayer.currentLanguage] || STEP_START_MESSAGES.english;
    const startMsg = startMsgs[event.step] || `Starting step ${event.step}`;
    ttsPlayer.speak(startMsg);

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

    // Narrate step failure
    ttsPlayer.speak(`Step ${event.step} failed. ${event.result?.error || ""}`);
  } else if (event.status === "completed") {
    badge.textContent = "✓";
    row.dataset.status = "completed";
    body.innerHTML = formatContent(summarizeStep(event.step, event.result));

    // Narrate step output
    let speechText = summarizeStep(event.step, event.result);
    if (event.step === 2 && event.result.applicable !== false) {
      speechText = `Visual analysis breakdown: ${event.result.real_pct}% real, ${event.result.edited_pct}% edited, and ${event.result.ai_generated_pct}% AI-generated. ${event.result.explanation}`;
    } else if (event.step === 3) {
      speechText = `Verdict: ${event.result.verdict}. Credibility score: ${event.result.score} out of 100. ${event.result.explanation}`;
    } else if (event.step === 4) {
      speechText = `Here are the actionable items: ${(event.result.actions || []).join(". ")}`;
    }
    ttsPlayer.speak(speechText);
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

//Snip Function
function initializeSnippingTool(sendResponse) {
  if (document.getElementById("snip-overlay")) return;

  // Append overlay CSS dynamically to Facebook page
  const style = document.createElement("style");
  style.id = "snip-styles";
  style.innerHTML = `
    #snip-overlay {
      position: fixed;
      top: 0; left: 0; width: 100vw; height: 100vh;
      background: rgba(15, 23, 42, 0.45);
      z-index: 99999999 !important;
      cursor: crosshair;
    }
    #snip-box {
      border: 2px dashed #3b82f6;
      background: rgba(59, 130, 246, 0.15);
      position: absolute; /* Changed to absolute to anchor to page scroll */
      pointer-events: none;
      display: none;
      box-shadow: 0 0 10px rgba(59, 130, 246, 0.3);
      z-index: 999999999 !important; /* Above the overlay */
    }
    .snip-popup-panel {
      position: fixed;
      bottom: 24px; right: 24px;
      width: 380px; max-height: 500px;
      background: #1e293b; color: #f1f5f9;
      border-radius: 16px; border: 1px solid #334155;
      box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.3);
      z-index: 999999999 !important;
      font-family: system-ui, -apple-system, sans-serif;
      display: flex; flex-direction: column; overflow: hidden;
    }
    .snip-popup-header {
      background: #0f172a; padding: 12px 16px;
      display: flex; justify-content: space-between; align-items: center;
      border-bottom: 1px solid #334155;
    }
    .snip-popup-content {
      padding: 16px; overflow-y: auto; flex-grow: 1;
    }
    .snip-btn-primary {
      background: #2563eb; color: white; padding: 8px 12px;
      border-radius: 8px; font-weight: 500; font-size: 12px;
      cursor: pointer; border: none; text-align: center;
    }
    .snip-btn-secondary {
      background: #334155; color: #cbd5e1; padding: 8px 12px;
      border-radius: 8px; font-size: 12px; cursor: pointer; border: none;
    }
  `;
  document.head.appendChild(style);

  // Overlay covers viewport to catch mouse events
  const overlay = document.createElement("div");
  overlay.id = "snip-overlay";
  
  // Snip box appended to body so it scrolls with the page
  const snipBox = document.createElement("div");
  snipBox.id = "snip-box";
  
  document.body.appendChild(snipBox);
  document.body.appendChild(overlay);

  let startPageX, startPageY;
  let lastMouseX = 0, lastMouseY = 0;
  let isDrawing = false;
  let autoScrollSpeed = 0;

  // Redraws the box continuously, factoring in any page scrolling
  function updateBox() {
    if (!isDrawing) return;
    
    // Calculate current global document coordinates
    const currentPageX = lastMouseX + window.scrollX;
    const currentPageY = lastMouseY + window.scrollY;

    const width = Math.abs(currentPageX - startPageX);
    const height = Math.abs(currentPageY - startPageY);
    
    snipBox.style.width = width + "px";
    snipBox.style.height = height + "px";
    snipBox.style.left = Math.min(currentPageX, startPageX) + "px";
    snipBox.style.top = Math.min(currentPageY, startPageY) + "px";
  }

  // Animation frame loop handling the auto-scrolling engine
  function scrollLoop() {
    if (!isDrawing) return;

    if (autoScrollSpeed !== 0) {
      window.scrollBy(0, autoScrollSpeed);
    }
    
    updateBox();
    requestAnimationFrame(scrollLoop);
  }

  overlay.addEventListener("mousedown", (e) => {
    isDrawing = true;
    
    // Anchor the start position to the page, not the screen
    startPageX = e.clientX + window.scrollX;
    startPageY = e.clientY + window.scrollY;
    
    lastMouseX = e.clientX;
    lastMouseY = e.clientY;

    snipBox.style.left = startPageX + "px";
    snipBox.style.top = startPageY + "px";
    snipBox.style.width = "0px";
    snipBox.style.height = "0px";
    snipBox.style.display = "block";

    // Kick off the drawing and scrolling monitor
    requestAnimationFrame(scrollLoop);
  });

  overlay.addEventListener("mousemove", (e) => {
    if (!isDrawing) return;
    
    lastMouseX = e.clientX;
    lastMouseY = e.clientY;

    // Detect if mouse is near the top or bottom of the screen (60px threshold)
    const edgeThreshold = 60;
    if (lastMouseY > window.innerHeight - edgeThreshold) {
      // Scroll down based on how close to the edge you are
      autoScrollSpeed = 15;
    } else if (lastMouseY < edgeThreshold) {
      // Scroll up
      autoScrollSpeed = -15;
    } else {
      autoScrollSpeed = 0;
    }
  });

    overlay.addEventListener("mouseup", (e) => {
      if (!isDrawing) return;
      isDrawing = false;
      autoScrollSpeed = 0;
      
      const endPageX = e.clientX + window.scrollX;
      const endPageY = e.clientY + window.scrollY;

      // Cleanup UI
      overlay.remove();
      snipBox.remove();

      // Original scroll position
      const originalScrollX = window.scrollX;
      const originalScrollY = window.scrollY;

      const minPageX = Math.min(startPageX, endPageX);
      const minPageY = Math.min(startPageY, endPageY);
      const width = Math.abs(endPageX - startPageX);
      const height = Math.abs(endPageY - startPageY);

      if (width < 10 || height < 10) return;

      // Scroll the viewport to the top-left of the selection area to ensure capture has it fully visible
      window.scrollTo(minPageX, minPageY);

      // Brief delay to allow browser repaint/rendering at the new scroll position
      setTimeout(() => {
        // Calculate crop coordinates relative to the actual scroll position achieved by the browser
        // (accounts for horizontal/vertical scroll limits on the page)
        const actualScrollX = window.scrollX;
        const actualScrollY = window.scrollY;

        const captureCropRect = {
          left: minPageX - actualScrollX,
          right: Math.max(startPageX, endPageX) - actualScrollX,
          top: minPageY - actualScrollY,
          bottom: Math.max(startPageY, endPageY) - actualScrollY,
          width: width,
          height: height
        };

        sendResponse({
          pageUrl: location.href,
          selectedText: null, // No manual text scraping
          cropRect: captureCropRect,
          originalScrollX: originalScrollX,
          originalScrollY: originalScrollY
        });
      }, 50);
      
    });
  }

function cropScreenshot(dataUrl, cropRect) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement("canvas");
      const ratio = window.devicePixelRatio || 1;
      
      canvas.width = cropRect.width * ratio;
      canvas.height = cropRect.height * ratio;
      
      const ctx = canvas.getContext("2d");
      ctx.drawImage(
        img,
        cropRect.left * ratio,
        cropRect.top * ratio,
        cropRect.width * ratio,
        cropRect.height * ratio,
        0,
        0,
        cropRect.width * ratio,
        cropRect.height * ratio
      );
      resolve(canvas.toDataURL("image/png"));
    };
    img.onerror = () => resolve(null);
    img.src = dataUrl;
  });
}

function isIntersecting(r1, r2) {
  return !(r2.left > r1.right || 
           r2.right < r1.left || 
           r2.top > r1.bottom || 
           r2.bottom < r1.top);
}

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

class TTSPlayer {
  constructor() {
    this.enabled = false;
    this.currentLanguage = "english";
    this.utteranceQueue = [];
    this.isSpeaking = false;
    this.voices = [];

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
      "cebuano": "fil-PH",
      "bisaya": "fil-PH",
      "ilocano": "fil-PH"
    };
    return map[lang.toLowerCase()] || "en-US";
  }

  speak(text) {
    if (!this.enabled || !text) return;

    const cleanText = text
      .replace(/<[^>]*>/g, "")
      .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, "$1")
      .replace(/\*\*([^*]+)\*\*/g, "$1")
      .replace(/[\*\#\_]/g, "")
      .trim();

    if (!cleanText) return;

    const sentences = cleanText.split(/[.!?；。]+/);
    for (const sentence of sentences) {
      const trimmed = sentence.trim();
      if (trimmed.length > 0) {
        this.enqueue(trimmed);
      }
    }
  }

  enqueue(text) {
    this.utteranceQueue.push(text);
    this.processQueue();
  }

  processQueue() {
    if (this.isSpeaking || this.utteranceQueue.length === 0 || !window.speechSynthesis) return;

    this.isSpeaking = true;
    const text = this.utteranceQueue.shift();
    const utterance = new SpeechSynthesisUtterance(text);
    const locale = this.getLocaleCode(this.currentLanguage);
    utterance.lang = locale;

    const matchingVoice = this.voices.find(v => v.lang.startsWith(locale) || v.lang.includes(locale.split("-")[0]));
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

const ttsPlayer = new TTSPlayer();
