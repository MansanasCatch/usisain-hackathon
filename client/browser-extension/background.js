// background.js — registers the right-click menu, builds the request,
// and streams the backend's SSE response into the content script's panel.

const BACKEND = "http://localhost:8000";
const DEFAULT_LANGUAGE = "english"; // fallback if no language saved in chrome.storage yet

chrome.runtime.onInstalled.addListener(() => {
  // Use a parent menu item so sub-items nest under one entry
  chrome.contextMenus.create({
    id: "usisain-parent",
    title: "UsisAIn — Trust  Fraud Detector",
    contexts: ["image", "selection", "page", "video"],
  });
  chrome.contextMenus.create({ id: "analyzeimage", parentId: "usisain-parent", title: "Usisain ang imahe", contexts: ["image"] });
  chrome.contextMenus.create({ id: "analyzetext", parentId: "usisain-parent", title: "Usisain ang text", contexts: ["selection"] });
  chrome.contextMenus.create({ id: "analyzevideo", parentId: "usisain-parent", title: "Usisain ang video", contexts: ["video"] });
  chrome.contextMenus.create({id: "snip-extract", parentId: "usisain-parent", title: "Usisain Snipping", contexts: ["all"]});
});


// ---------------------------------------------------------------------------
// Helpers to ensure the content script is loaded before sending messages
// ---------------------------------------------------------------------------

/**
 * Injects site-selectors.js + content.js into `tabId` if they aren't already
 * loaded. Uses a "ping" message: if the content script responds, it's alive;
 * otherwise we inject it with chrome.scripting.executeScript().
 */
async function ensureContentScript(tabId) {
  try {
    const response = await chrome.tabs.sendMessage(tabId, { action: "ping" });
    if (response && response.pong) return; // already alive
  } catch {
    // content script not loaded — inject it
  }

  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ["site-selectors.js", "content.js"],
    });
    // Give the content script a moment to initialize its listener
    await new Promise(resolve => setTimeout(resolve, 100));
  } catch (err) {
    console.warn("[UsisAIn] Could not inject content script:", err.message);
    throw new Error("Cannot inject content script on this page. Chrome internal pages (chrome://, chrome-extension://) are not supported.");
  }
}

/**
 * Safely send a message to a tab's content script, ensuring it's injected first.
 * Returns null if the message can't be delivered (instead of throwing).
 */
async function safeSendMessage(tabId, message) {
  try {
    await ensureContentScript(tabId);
    return await chrome.tabs.sendMessage(tabId, message);
  } catch (err) {
    console.warn(`[UsisAIn] sendMessage(${message.action}) failed:`, err.message);
    return null;
  }
}


// ---------------------------------------------------------------------------
// Context menu handler
// ---------------------------------------------------------------------------

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (!tab?.id) return;
  
  try {
    const storage = await chrome.storage.local.get("preferredLanguage");
    const selectedLanguage = storage.preferredLanguage || DEFAULT_LANGUAGE;
    const form = new FormData();
    form.append("language", selectedLanguage);
    if (info.menuItemId === "snip-extract") {
      const extractedData = await safeSendMessage(tab.id, { action: "start-snipping" });
      if (!extractedData) return;
      form.append("source_url", extractedData.pageUrl || tab.url || "");
      form.append("text", extractedData.selectedText || "");
      
      if (extractedData.images && extractedData.images.length > 0) {
        for (let i = 0; i < extractedData.images.length; i++) {
          const img = extractedData.images[i];
          
          const fetchResponse = await fetch(img.base64);
          const blob = await fetchResponse.blob();
          
          const urlFilename = img.url.split('/').pop().split('?')[0];
          const filename = urlFilename || `image_${i}.png`;

          form.append('file', blob, filename);
        }
      }
      try {
        await streamAnalysis(tab.id, form);
      } finally {
        // Clear upload banner
        try { await safeSendMessage(tab.id, { action: 'upload-end' }); } catch (e) { }
      }
    } else {
      // Ensure content script is injected, then ask it for page context
      const context = await safeSendMessage(tab.id, { action: "get-context", srcUrl: info.srcUrl });
      if (!context) {
        console.error("[UsisAIn] Could not get context from content script.");
        return;
      }

      form.append("source_url", context.pageUrl || tab.url || "");

      if (info.menuItemId === "analyzetext") {
        const text = info.selectionText || context.selectedText || context.postCaption;
        if (!text) return;
        form.append("text", text);
      }

      if (info.menuItemId === "analyzeimage") {
        const url = info.srcUrl || context.clickedImageSrc;
        if (!url) return;
        const blob = await fetchAndResizeBlob(tab.id, url, 1024, 0.75);
        form.append("file", blob, "image.png");
      }

      if (info.menuItemId === "analyzevideo") {
        const url = info.srcUrl || context.clickedVideoSrc;
        if (!url) return;
        if (url.startsWith("blob:")) {
          await safeSendMessage(tab.id, { action: "pipeline-error", error: "This video uses a blob: stream and can't be fetched directly. See README known limitations." });
          return;
        }
        const blob = await fetchAndResizeBlob(tab.id, url, 1024, 0.75);
        form.append("file", blob, "video.mp4");
      }

      if (info.menuItemId === "analyzepost") {
        const caption = context.postCaption || context.selectedText || "";
        form.append("caption", caption);
        const imgUrl = info.srcUrl || context.postImages?.[0] || context.clickedImageSrc;
        if (imgUrl) {
          const blob = await fetchAndResizeBlob(tab.id, imgUrl, 1024, 0.75);
          form.append("file", blob, "image.png");
        }
      }

      // Notify content script we're starting the upload (for UI banner)
      try {
        await safeSendMessage(tab.id, { action: 'upload-start' });
      } catch (e) {
        // ignore
      }

      try {
        await streamAnalysis(tab.id, form);
      } finally {
        // Clear upload banner
        try { await safeSendMessage(tab.id, { action: 'upload-end' }); } catch (e) { }
      }
    }

    
  } catch (err) {
    console.error("[UsisAIn] Pipeline error:", err);
    await safeSendMessage(tab.id, { action: "pipeline-error", error: err.message });
  }
});


// ---------------------------------------------------------------------------
// Fetch helper — asks the content script to fetch a cross-origin resource
// ---------------------------------------------------------------------------

async function fetchAsBlob(tabId, url) {
  // Deprecated: kept for backward compatibility
  const res = await safeSendMessage(tabId, { action: "fetch-as-dataurl", url });
  if (!res || res.error) throw new Error(res?.error || "Failed to fetch resource from page");
  return await (await fetch(res.dataUrl)).blob();
}

async function fetchAndResizeBlob(tabId, url, maxDim = 1024, quality = 0.75) {
  const res = await safeSendMessage(tabId, { action: "fetch-and-resize", url, maxDim, quality });
  if (!res || res.error) throw new Error(res?.error || "Failed to fetch/resize resource from page");
  return await (await fetch(res.dataUrl)).blob();
}


// ---------------------------------------------------------------------------
// SSE stream — sends backend results to the content script panel step by step
// ---------------------------------------------------------------------------

async function getBackendSettings() {
  try {
    const response = await fetch(`${BACKEND}/api/settings`);
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  }
}

async function streamAnalysis(tabId, form) {
  const settings = await getBackendSettings();
  const selectedLanguage = form.get("language") || "english";
  if (settings) {
    await safeSendMessage(tabId, {
      action: "pipeline-settings",
      pipeline_step_timeout_seconds: Number(settings.pipeline_step_timeout_seconds) || 120,
      tts_enabled: settings.tts_enabled !== undefined ? settings.tts_enabled : false,
      language: selectedLanguage,
    });
  }

  await safeSendMessage(tabId, { action: "pipeline-start" });

  let response;
  try {
    response = await fetch(`${BACKEND}/api/analyze/stream`, { method: "POST", body: form });
  } catch (err) {
    await safeSendMessage(tabId, { action: "pipeline-error", error: `Cannot reach backend at ${BACKEND}. Is it running? (${err.message})` });
    return;
  }

  if (!response.ok || !response.body) {
    const errorText = await response.text().catch(() => "");
    await safeSendMessage(tabId, { action: "pipeline-error", error: `Backend returned ${response.status}. ${errorText || "Is it running on localhost:8000?"}` });
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary;
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      if (!frame.startsWith("data: ")) continue;

      try {
        const payload = JSON.parse(frame.slice(6));
        if (payload.done) continue; // final marker, nothing to render
        if (payload.error && !payload.step) {
          // Top-level system error (e.g. quota exceeded)
          await safeSendMessage(tabId, { action: "pipeline-error", error: payload.error });
          continue;
        }
        await safeSendMessage(tabId, { action: "pipeline-event", event: payload });
      } catch (parseErr) {
        console.warn("[UsisAIn] Could not parse SSE frame:", frame, parseErr);
      }
    }
  }
}
