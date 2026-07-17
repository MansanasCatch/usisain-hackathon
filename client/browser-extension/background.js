// background.js — registers the right-click menu, builds the request,
// and streams the backend's SSE response into the content script's panel.

const BACKEND = "http://localhost:8000";
const DEFAULT_LANGUAGE = "english"; // fallback if no language saved in chrome.storage yet

const activeTabAbortControllers = new Map();

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "cancel-analysis") {
    const tabId = sender.tab?.id;
    if (tabId && activeTabAbortControllers.has(tabId)) {
      console.log(`[UsisAIn] Aborting active analysis due to close request from tab ${tabId}`);
      try {
        activeTabAbortControllers.get(tabId).abort();
      } catch (e) {
        console.error(e);
      }
      activeTabAbortControllers.delete(tabId);
    }
  }
});

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
    const storage = await chrome.storage.local.get(["preferredLanguage", "useOcr"]);
    const selectedLanguage = storage.preferredLanguage || DEFAULT_LANGUAGE;
    const useOcr = storage.useOcr !== undefined ? storage.useOcr : true;
    const form = new FormData();
    form.append("language", selectedLanguage);
    form.append("use_ocr", useOcr.toString());

    let previewText = null;
    let previewImageUrl = null;

    if (info.menuItemId === "snip-extract") {
      const extractedData = await safeSendMessage(tab.id, { action: "start-snipping" });
      if (!extractedData || !extractedData.cropRect) return;
      
      form.append("source_url", extractedData.pageUrl || tab.url || "");
      
      let dataUrl;
      try {
        dataUrl = await chrome.tabs.captureVisibleTab(null, { format: "png" });
      } catch (err) {
        console.error("[UsisAIn] captureVisibleTab failed:", err.message);
      }
      
      if (extractedData.originalScrollX !== undefined && extractedData.originalScrollY !== undefined) {
        await safeSendMessage(tab.id, {
          action: "restore-scroll",
          scrollX: extractedData.originalScrollX,
          scrollY: extractedData.originalScrollY
        });
      }
      
      if (dataUrl) {
        // Send screenshot back to content script to crop it with canvas
        const cropRes = await safeSendMessage(tab.id, {
          action: "crop-screenshot",
          dataUrl: dataUrl,
          cropRect: extractedData.cropRect
        });
        
        if (cropRes && cropRes.croppedDataUrl) {
          const fetchResponse = await fetch(cropRes.croppedDataUrl);
          const blob = await fetchResponse.blob();
          form.append("file", blob, "snip.png");
          previewImageUrl = cropRes.croppedDataUrl;
        }
      }
      
      // Append text as caption if we have an image file, otherwise as text
      if (extractedData.selectedText) {
        if (form.has("file")) {
          form.append("caption", extractedData.selectedText);
          previewText = extractedData.selectedText;
        } else {
          form.append("text", extractedData.selectedText);
          previewText = extractedData.selectedText;
        }
      }
      
      try {
        await streamAnalysis(tab.id, form, previewText, previewImageUrl);
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
        previewText = text;
      }

      if (info.menuItemId === "analyzeimage") {
        const url = info.srcUrl || context.clickedImageSrc;
        if (!url) return;
        const { blob, dataUrl } = await fetchAndResizeBlob(tab.id, url, 1024, 0.75);
        form.append("file", blob, "image.png");
        previewImageUrl = dataUrl;
      }

      if (info.menuItemId === "analyzevideo") {
        const url = info.srcUrl || context.clickedVideoSrc;
        if (!url) return;
        if (url.startsWith("blob:")) {
          await safeSendMessage(tab.id, { action: "pipeline-error", error: "This video uses a blob: stream and can't be fetched directly. See README known limitations." });
          return;
        }
        const { blob, dataUrl } = await fetchAndResizeBlob(tab.id, url, 1024, 0.75);
        form.append("file", blob, "video.mp4");
        previewImageUrl = dataUrl;
      }

      if (info.menuItemId === "analyzepost") {
        const caption = context.postCaption || context.selectedText || "";
        form.append("caption", caption);
        previewText = caption;
        const imgUrl = info.srcUrl || context.postImages?.[0] || context.clickedImageSrc;
        if (imgUrl) {
          const { blob, dataUrl } = await fetchAndResizeBlob(tab.id, imgUrl, 1024, 0.75);
          form.append("file", blob, "image.png");
          previewImageUrl = dataUrl;
        }
      }

      // Notify content script we're starting the upload (for UI banner)
      try {
        await safeSendMessage(tab.id, { action: 'upload-start' });
      } catch (e) {
        // ignore
      }

      try {
        await streamAnalysis(tab.id, form, previewText, previewImageUrl);
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
  const blob = await (await fetch(res.dataUrl)).blob();
  return { blob, dataUrl: res.dataUrl };
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

async function streamAnalysis(tabId, form, previewText, previewImageUrl) {
  // If there's an existing active AbortController for this tab, abort it first
  if (activeTabAbortControllers.has(tabId)) {
    console.log(`[UsisAIn] Aborting existing analysis stream for tab ${tabId}`);
    try {
      activeTabAbortControllers.get(tabId).abort();
    } catch (e) {
      console.error(e);
    }
    activeTabAbortControllers.delete(tabId);
  }

  const controller = new AbortController();
  activeTabAbortControllers.set(tabId, controller);

  const settings = await getBackendSettings();
  const selectedLanguage = form.get("language") || "english";

  // Get local settings first
  let useTts = false;
  let selectedVoice = null;
  if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
    const localData = await chrome.storage.local.get(["useTts", "selectedVoice"]);
    useTts = localData.useTts !== undefined ? localData.useTts : false;
    selectedVoice = localData.selectedVoice || null;
  }

  if (settings) {
    await safeSendMessage(tabId, {
      action: "pipeline-settings",
      pipeline_step_timeout_seconds: Number(settings.pipeline_step_timeout_seconds) || 120,
      tts_enabled: useTts,
      selected_voice: selectedVoice,
      language: selectedLanguage,
    });
  }

  await safeSendMessage(tabId, { 
    action: "pipeline-start",
    previewText,
    previewImageUrl
  });

  try {
    const response = await fetch(`${BACKEND}/api/analyze/stream`, { 
      method: "POST", 
      body: form,
      signal: controller.signal
    });

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
            await safeSendMessage(tabId, { action: "pipeline-error", error: payload.error });
            continue;
          }
          await safeSendMessage(tabId, { action: "pipeline-event", event: payload });
        } catch (parseErr) {
          console.warn("[UsisAIn] Could not parse SSE frame:", frame, parseErr);
        }
      }
    }
  } catch (err) {
    if (err.name === 'AbortError') {
      console.log(`[UsisAIn] Stream for tab ${tabId} successfully aborted.`);
      return;
    }
    console.error("[UsisAIn] Stream error:", err);
    await safeSendMessage(tabId, { action: "pipeline-error", error: `Cannot reach backend at ${BACKEND}. Is it running? (${err.message})` });
  } finally {
    if (activeTabAbortControllers.get(tabId) === controller) {
      activeTabAbortControllers.delete(tabId);
    }
  }
}
