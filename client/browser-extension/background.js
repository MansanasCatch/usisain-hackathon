// background.js — registers the right-click menu, builds the request,
// and streams the backend's SSE response into the content script's panel.

const BACKEND = "http://localhost:8000";
const DEFAULT_LANGUAGE = "taglish"; // change via chrome.storage if you add a settings UI later

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({ id: "analyzetext", title: "Analyze this text", contexts: ["selection"] });
  chrome.contextMenus.create({ id: "analyzeimage", title: "Analyze this image", contexts: ["image"] });
  chrome.contextMenus.create({ id: "analyzevideo", title: "Analyze this video (local file src only)", contexts: ["video"] });
  chrome.contextMenus.create({ id: "analyzepost", title: "Analyze this post (text + image)", contexts: ["image", "page", "selection"] });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (!tab?.id) return;
  const context = await chrome.tabs.sendMessage(tab.id, { action: "get-context", srcUrl: info.srcUrl });

  try {
    const form = new FormData();
    form.append("language", DEFAULT_LANGUAGE);
    form.append("source_url", context.pageUrl);

    if (info.menuItemId === "analyzetext") {
      const text = info.selectionText || context.selectedText || context.postCaption;
      if (!text) return;
      form.append("text", text);
    }

    if (info.menuItemId === "analyzeimage") {
      const url = info.srcUrl || context.clickedImageSrc;
      if (!url) return;
      const blob = await fetchAsBlob(tab.id, url);
      form.append("file", blob, "image.png");
    }

    if (info.menuItemId === "analyzevideo") {
      const url = info.srcUrl || context.clickedVideoSrc;
      if (!url) return;
      if (url.startsWith("blob:")) {
        chrome.tabs.sendMessage(tab.id, { action: "pipeline-error", error: "This video uses a blob: stream and can't be fetched directly. See README known limitations." });
        return;
      }
      const blob = await fetchAsBlob(tab.id, url);
      form.append("file", blob, "video.mp4");
    }

    if (info.menuItemId === "analyzepost") {
      const caption = context.postCaption || context.selectedText || "";
      form.append("caption", caption);
      const imgUrl = info.srcUrl || context.postImages?.[0] || context.clickedImageSrc;
      if (imgUrl) {
        const blob = await fetchAsBlob(tab.id, imgUrl);
        form.append("file", blob, "image.png");
      }
    }

    await streamAnalysis(tab.id, form);
  } catch (err) {
    chrome.tabs.sendMessage(tab.id, { action: "pipeline-error", error: err.message });
  }
});

async function fetchAsBlob(tabId, url) {
  const res = await chrome.tabs.sendMessage(tabId, { action: "fetch-as-dataurl", url });
  if (res.error) throw new Error(res.error);
  return await (await fetch(res.dataUrl)).blob();
}

async function streamAnalysis(tabId, form) {
  chrome.tabs.sendMessage(tabId, { action: "pipeline-start" });

  const response = await fetch(`${BACKEND}/api/analyze/stream`, { method: "POST", body: form });
  if (!response.ok || !response.body) {
    chrome.tabs.sendMessage(tabId, { action: "pipeline-error", error: `Backend returned ${response.status}. Is it running on localhost:8000?` });
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

      const payload = JSON.parse(frame.slice(6));
      if (payload.done) continue; // final marker, nothing to render
      chrome.tabs.sendMessage(tabId, { action: "pipeline-event", event: payload });
    }
  }
}
