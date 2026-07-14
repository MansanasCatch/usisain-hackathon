const BACKEND = "http://localhost:8000";

// ---------- Language Preference ----------
const languageSelect = document.getElementById("language-select");

// Load saved language
chrome.storage.local.get("preferredLanguage", (data) => {
  if (data.preferredLanguage) {
    languageSelect.value = data.preferredLanguage;
  }
});

// Save language on change
languageSelect.addEventListener("change", () => {
  chrome.storage.local.set({ preferredLanguage: languageSelect.value });
});

async function loadHistory() {
  const statusEl = document.getElementById("status");
  const list = document.getElementById("history");
  try {
    const scans = await fetch(`${BACKEND}/api/scans?limit=15`).then(r => r.json());
    statusEl.textContent = scans.length ? "Recent scans (all channels)" : "No scans yet — right-click text or an image to start.";
    list.innerHTML = "";
    for (const s of scans) {
      const li = document.createElement("li");
      li.innerHTML = `<div class="top-row"><span>${s.channel}</span><span>${s.step3_verdict ?? "—"}</span></div>
        <div>${(s.input_summary || "").slice(0, 70)}</div>`;
      list.appendChild(li);
    }
  } catch {
    statusEl.textContent = "Can't reach backend — is it running on localhost:8000?";
  }
}
loadHistory();
