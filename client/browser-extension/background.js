// Chromium service workers load the shim here; Firefox lists it in background.scripts.
if (typeof globalThis.usisainExt === "undefined" && typeof importScripts === "function") {
  importScripts("compat.js");
}
const menusApi = globalThis.usisainExt ? globalThis.usisainExt.menus : undefined;

const BACKEND = "http://localhost:8000";
const DEFAULT_LANGUAGE = "english"; 

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

chrome.runtime.onInstalled.addListener((details) => {
  // Automatically navigate to the app dashboard upon extension installation
  if (details && details.reason === "install") {
    try {
      chrome.tabs.create({ url: `${BACKEND}/app/dashboard` });
    } catch (err) {
      console.warn("[UsisAIn] Could not open dashboard tab on install:", err);
    }
  }

  if (!menusApi) {
    console.warn("[UsisAIn] Context menus API is not available in this browser.");
    return;
  }
  menusApi.create({
    id: "usisain-parent",
    title: "UsisAIn — Trust  Fraud Detector",
    contexts: ["image", "selection", "page", "video"],
  });
  menusApi.create({ id: "analyzeimage", parentId: "usisain-parent", title: "Usisain ang imahe", contexts: ["image"] });
  menusApi.create({ id: "analyzetext", parentId: "usisain-parent", title: "Usisain ang text", contexts: ["selection"] });
  menusApi.create({ id: "analyzevideo", parentId: "usisain-parent", title: "Usisain ang video", contexts: ["video"] });
  menusApi.create({id: "snip-extract", parentId: "usisain-parent", title: "Usisain Snipping", contexts: ["all"]});
});







async function ensureContentScript(tabId) {
  try {
    const response = await chrome.tabs.sendMessage(tabId, { action: "ping" });
    if (response && response.pong) return; 
  } catch {
    
  }

  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ["site-selectors.js", "content.js"],
    });
    
    await new Promise(resolve => setTimeout(resolve, 100));
  } catch (err) {
    console.warn("[UsisAIn] Could not inject content script:", err.message);
    throw new Error("Cannot inject content script on this page. Chrome internal pages (chrome://, chrome-extension://) are not supported.");
  }
}


async function safeSendMessage(tabId, message) {
  try {
    await ensureContentScript(tabId);
    return await chrome.tabs.sendMessage(tabId, message);
  } catch (err) {
    console.warn(`[UsisAIn] sendMessage(${message.action}) failed:`, err.message);
    return null;
  }
}






function isVisionModel(name, provider) {
  if (!name) return false;
  const p = (provider || "").toLowerCase();
  if (p === "gemini") return true;
  const lower = name.toLowerCase();
  const visionKeywords = ["vision", "moondream", "llava", "bakllava", "minicpm-v", "scout", "multimodal", "-vl", "vl-", "_vl"];
  return visionKeywords.some(kw => lower.includes(kw));
}

function getActiveModelName(storage) {
  const provider = (storage.activeProvider || "ollama").toLowerCase();
  if (provider === "grok") return storage.activeGrokModel || "gpt-oss-120b";
  if (provider === "gemini") return storage.activeGeminiModel || "gemini-3.5-flash";
  if (provider === "ollama") return storage.activeOllamaModel || "llama3.2:1b";
  return "";
}

if (menusApi) menusApi.onClicked.addListener(async (info, tab) => {
  if (!tab?.id) return;
  
  try {
    const storage = await chrome.storage.local.get([
      "preferredLanguage",
      "useOcr",
      "activeProvider",
      "activeGrokModel",
      "activeGeminiModel",
      "activeOllamaModel"
    ]);
    const selectedLanguage = storage.preferredLanguage || DEFAULT_LANGUAGE;
    const useOcr = storage.useOcr !== undefined ? storage.useOcr : true;
    const activeProvider = (storage.activeProvider || "ollama").toLowerCase();
    const activeModel = getActiveModelName(storage);
    const hasVision = isVisionModel(activeModel, activeProvider);

    if (info.menuItemId === "snip-extract" || info.menuItemId === "analyzeimage") {
      // If Tesseract-OCR is enabled or provider is Ollama (which routes images to moondream),
      // image analysis is fully supported even with text-only active models.
      // Only block if the model is Text-Only AND Tesseract-OCR is disabled AND provider is not Ollama.
      if (!hasVision && !useOcr && activeProvider !== "ollama") {
        const errorMsg = `Cannot analyze image: The active model "${activeModel}" (${activeProvider.toUpperCase()}) is Text-Only and Tesseract-OCR is disabled. Please enable Tesseract-OCR or switch to a Vision-supported model (such as Google Gemini or a model with the 👁️ Vision badge in the UsisAIn popup) to analyze images.`;
        await safeSendMessage(tab.id, {
          action: "pipeline-error",
          error: errorMsg
        });
        return;
      }
    }

    const form = new FormData();
    form.append("language", selectedLanguage);
    form.append("use_ocr", useOcr.toString());
    if (storage.activeProvider) {
      form.append("provider", storage.activeProvider);
    }

    let previewText = null;
    let previewImageUrl = null;

    if (info.menuItemId === "snip-extract") {
      const extractedData = await safeSendMessage(tab.id, { action: "start-snipping" });
      if (!extractedData || !extractedData.cropRect) return;
      
      form.append("source_url", extractedData.pageUrl || tab.url || "");
      
      let dataUrl;
      try {
        if (globalThis.usisainExt && globalThis.usisainExt.has("tabs.captureVisibleTab")) {
          dataUrl = await chrome.tabs.captureVisibleTab(null, { format: "png" });
        } else {
          console.warn("[UsisAIn] tabs.captureVisibleTab is not available in this browser.");
        }
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
        
        try { await safeSendMessage(tab.id, { action: 'upload-end' }); } catch (e) { }
      }
    } else {
      
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

      
      try {
        await safeSendMessage(tab.id, { action: 'upload-start' });
      } catch (e) {
        
      }

      try {
        await streamAnalysis(tab.id, form, previewText, previewImageUrl);
      } finally {
        
        try { await safeSendMessage(tab.id, { action: 'upload-end' }); } catch (e) { }
      }
    }

    
  } catch (err) {
    console.error("[UsisAIn] Pipeline error:", err);
    await safeSendMessage(tab.id, { action: "pipeline-error", error: err.message });
  }
});






async function fetchAsBlob(tabId, url) {
  
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
          if (payload.done) continue; 
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
