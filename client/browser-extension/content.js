// content.js — runs in the page. Handles two jobs:
//   1. Tracking the right-clicked element and extracting page/post context.
//   2. Rendering the progressive 5-step results panel as events stream in
//      from background.js (which does the actual fetch to the backend).

let lastRightClickedEl = null;
document.addEventListener("contextmenu", (e) => { lastRightClickedEl = e.target; }, true);

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
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

  if (message.action === "pipeline-start") { showPanel(); return; }
  if (message.action === "pipeline-event") { updatePanelStep(message.event); return; }
  if (message.action === "pipeline-error") { showPanelError(message.error); return; }
});

// ---------- results panel ----------

const STEP_LABELS = {
  1: "AI Insights", 2: "Content Analyser", 3: "Legit or Fake",
  4: "Actionable Items", 5: "Learnings",
};

function showPanel() {
  document.getElementById("usisain-panel")?.remove();

  const panel = document.createElement("div");
  panel.id = "usisain-panel";
  Object.assign(panel.style, {
    position: "fixed", bottom: "20px", right: "20px", width: "340px", maxHeight: "70vh",
    overflowY: "auto", zIndex: 999999, background: "#171a21", color: "#e7e9ee",
    borderRadius: "12px", boxShadow: "0 8px 30px rgba(0,0,0,0.5)", fontFamily: "system-ui, sans-serif",
    fontSize: "13px", padding: "12px",
  });

  const header = document.createElement("div");
  header.textContent = "UsisAIn — analyzing…";
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

function updatePanelStep(event) {
  const row = document.getElementById(`usisain-step-${event.step}`);
  if (!row) return;
  const icon = row.querySelector(".usisain-icon");
  const body = row.querySelector(".usisain-body");

  if (event.status === "in_progress") {
    icon.textContent = "🔄";
    body.textContent = "Working…";
  } else if (event.status === "error") {
    icon.textContent = "⚠️";
    body.textContent = event.result?.error || "Something went wrong on this step.";
  } else if (event.status === "completed") {
    icon.textContent = "✅";
    body.textContent = summarizeStep(event.step, event.result);
  }
}

function summarizeStep(step, result) {
  if (!result) return "Done.";
  if (step === 1) return result.insight || "No insight generated.";
  if (step === 2) {
    if (result.applicable === false) return result.explanation;
    return `${result.real_pct}% real · ${result.edited_pct}% edited · ${result.ai_generated_pct}% AI-generated`;
  }
  if (step === 3) return `${result.verdict} (score ${result.score}/100) — ${result.explanation}`;
  if (step === 4) return (result.actions || []).join(" · ") || "No actions generated.";
  if (step === 5) return result.learning_material || "No learnings generated.";
  return "Done.";
}

function showPanelError(error) {
  const panel = document.getElementById("usisain-panel");
  if (panel) panel.querySelector("div").textContent = `UsisAIn — error: ${error}`;
}
