// ---------- tabs ----------
document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll("main > section").forEach(s => s.style.display = "none");
    btn.classList.add("active");
    document.getElementById(`tab-${btn.dataset.tab}`).style.display = "block";
    if (btn.dataset.tab === "stepinfo") {
      loadStepInfo();
    }
  });
});
document.querySelector('[data-tab="overview"]').classList.add("active");

// ---------- overview ----------
async function loadOverview() {
  const summary = await ApiClient.getSummary();
  const cards = document.getElementById("summary-cards");
  cards.innerHTML = "";
  const items = [
    ["Total scans", summary.total_scans],
    ...Object.entries(summary.by_channel || {}).map(([k, v]) => [k, v]),
  ];
  for (const [label, value] of items) {
    cards.innerHTML += `<div class="card"><div class="value">${value}</div><div class="label">${label}</div></div>`;
  }

  const trend = await ApiClient.getTrends(30);
  const days = [...new Set(trend.map(t => t.day))].sort();
  const channels = [...new Set(trend.map(t => t.channel))];
  const colors = { extension: "#4f8cff", messenger: "#35c47c", webapp: "#c084fc" };

  try {
    if (typeof Chart === "undefined") {
      throw new ReferenceError("Chart.js library is not loaded.");
    }
    new Chart(document.getElementById("trend-chart"), {
      type: "line",
      data: {
        labels: days,
        datasets: channels.map(c => ({
          label: c,
          data: days.map(d => (trend.find(t => t.day === d && t.channel === c) || {}).c || 0),
          borderColor: colors[c] || "#888",
          tension: 0.3,
        })),
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { title: { display: true, text: "Scans over time", color: "#e7e9ee" }, legend: { labels: { color: "#9aa1ac" } } },
        scales: { x: { ticks: { color: "#9aa1ac" } }, y: { ticks: { color: "#9aa1ac" } } }
      },
    });

    new Chart(document.getElementById("verdict-chart"), {
      type: "doughnut",
      data: {
        labels: Object.keys(summary.by_verdict || {}),
        datasets: [{ data: Object.values(summary.by_verdict || {}), backgroundColor: ["#35c47c", "#e0b23d", "#e6584f", "#4f8cff"] }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { title: { display: true, text: "Verdicts", color: "#e7e9ee" }, legend: { labels: { color: "#9aa1ac" } } }
      },
    });
  } catch (err) {
    console.error("Dashboard visualization error:", err);
    // Display error fallback in chart boxes so user knows
    document.getElementById("trend-chart").parentElement.innerHTML = `<div style="padding:40px; text-align:center; color:var(--muted)">Visualization unavailable: ${err.message}</div>`;
    document.getElementById("verdict-chart").parentElement.innerHTML = `<div style="padding:40px; text-align:center; color:var(--muted)">Verdict distribution unavailable: ${err.message}</div>`;
  }
}

// ---------- scan history ----------
async function loadScans() {
  const channel = document.getElementById("filter-channel").value;
  const scans = await ApiClient.getScans({ channel, limit: 50 });
  const tbody = document.querySelector("#scans-table tbody");
  tbody.innerHTML = "";
  for (const s of scans) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${new Date(s.created_at + "Z").toLocaleString()}</td>
      <td>${s.channel}</td>
      <td>${s.content_type ?? "—"}</td>
      <td>${(s.input_summary || "").slice(0, 50)}</td>
      <td>${s.step2_score ?? "—"}</td>
      <td><span class="badge ${s.step3_verdict}">${s.step3_verdict || "—"}</span></td>`;
    tr.addEventListener("click", () => openModal(s.raw_result_json));
    tbody.appendChild(tr);
  }
}
document.getElementById("refresh-scans").addEventListener("click", loadScans);
document.getElementById("filter-channel").addEventListener("change", loadScans);
document.getElementById("clear-scans").addEventListener("click", async () => {
  if (confirm("Are you sure you want to clear all scan history? This will also clear the local RAG database cache.")) {
    await ApiClient.clearScans();
    loadScans();
    loadOverview();
  }
});

function openModal(rawJson) {
  document.getElementById("modal-body").textContent = JSON.stringify(JSON.parse(rawJson), null, 2);
  document.getElementById("detail-modal").classList.add("open");
}
document.getElementById("modal-close").addEventListener("click", () =>
  document.getElementById("detail-modal").classList.remove("open"));

// ---------- reference documents ----------
async function loadRefDocs() {
  const docs = await ApiClient.getReferenceDocuments();
  const grid = document.getElementById("refdoc-grid");
  grid.innerHTML = "";
  for (const d of docs) {
    grid.innerHTML += `
      <div class="ref-card">
        <span class="del" data-id="${d.id}">✕</span>
        <div><strong>${d.name}</strong></div>
        <div>${d.category}</div>
        <div style="color:var(--muted)">${new Date(d.uploaded_at + "Z").toLocaleDateString()}</div>
      </div>`;
  }
  grid.querySelectorAll(".del").forEach(el => {
    el.addEventListener("click", async () => {
      await ApiClient.deleteReferenceDocument(el.dataset.id);
      loadRefDocs();
    });
  });
}

document.getElementById("refdoc-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  await ApiClient.uploadReferenceDocument(new FormData(form));
  form.reset();
  loadRefDocs();
});

// ---------- error log ----------
async function loadErrors() {
  const errors = await ApiClient.getErrors(100);
  const tbody = document.querySelector("#errors-table tbody");
  tbody.innerHTML = "";
  document.getElementById("error-count").textContent = `${errors.length} error(s) logged`;

  for (const err of errors) {
    const tr = document.createElement("tr");
    const stepLabel = err.step_name
      ? `Step ${err.step} — ${err.step_name}`
      : (err.error_type === "system" ? "System" : "General");
    const shortMsg = err.error_msg.length > 120 ? err.error_msg.slice(0, 120) + "…" : err.error_msg;
    tr.innerHTML = `
      <td>${new Date(err.created_at + "Z").toLocaleString()}</td>
      <td>${stepLabel}</td>
      <td><span class="badge ${err.error_type === "system" ? "flagged" : "inconclusive"}">${err.error_type}</span></td>
      <td style="font-family:monospace; font-size:12px;">${shortMsg}</td>`;
    tr.addEventListener("click", () => openModal(JSON.stringify(err)));
    tbody.appendChild(tr);
  }
}

document.getElementById("refresh-errors").addEventListener("click", loadErrors);
document.getElementById("clear-errors").addEventListener("click", async () => {
  if (confirm("Clear all error logs?")) {
    await ApiClient.clearErrors();
    loadErrors();
  }
});

// ---------- init ----------
loadOverview();
loadScans();
loadRefDocs();
loadErrors();


// ---------- step info ----------
async function loadStepInfo() {
  const settings = await ApiClient.getSettings();

  const provider = settings.default_llm_provider || "ollama";
  const bannerBadge = document.getElementById("banner-provider-badge");
  bannerBadge.textContent = provider.toUpperCase();
  bannerBadge.className = `badge ${provider === "gemini" ? "likely_true" : "inconclusive"}`;

  const stepinfoCards = document.getElementById("stepinfo-cards");
  stepinfoCards.innerHTML = "";

  const steps = [
    {
      num: 1,
      name: "AI Insights — First-Pass Content Review",
      desc: `This step provides the initial rapid assessment of the submitted content. It adapts its analysis based on what the user submits:`,
      substeps: [
        `<strong>Text-only input:</strong> The LLM reads the raw text (e.g. a social media caption, forwarded message, or news headline) and summarizes what it says while flagging urgency language, emotional framing, unusual formatting, or unofficial/suspicious links.`,
        `<strong>Image input:</strong> When using Gemini, the multimodal LLM directly examines the image. Under the local Ollama provider, Tesseract OCR extracts the text overlays, and the text LLM analyzes the text content and OCR text.`,
        `<strong>Usisain Snipping:</strong> The user can drag a selection box over any part of a webpage to snip text and/or images. The extracted text and cropped images are sent together for a unified analysis.`,
        `<strong>Video input:</strong> The first frame of the video is extracted using OpenCV and analyzed. (For Gemini, the frame is passed directly; for Ollama, OCR text is extracted from the frame and analyzed).`,
      ],
      output: "A concise 2-4 sentence overview/summary that is passed to Steps 3, 4, and 5 as foundational context.",
      tech: ["LLM (text or vision)", "Tesseract OCR", "OpenCV (video frame extraction)"],
      timeout: `${settings.pipeline_step_timeout_seconds || 120} seconds`,
      get_model: (s) => s.default_llm_provider === "gemini" ? s.gemini_model : `${s.ollama_model} (text) / ${s.ollama_vision_model} (vision)`
    },
    {
      num: 2,
      name: "Content Analyser — Digital Image Forensics",
      desc: `This step applies <em>local, offline computer-vision heuristics</em> to determine whether an image or video has been edited, AI-generated, or is authentic. <strong>No network calls are made — this is the fastest step in the pipeline.</strong> If the input is text-only, this step is skipped (marked "not applicable").`,
      substeps: [
        `<strong>Error Level Analysis (ELA):</strong> The image is re-compressed at a known JPEG quality and the pixel-level difference is measured. Regions saved at a different compression quality than the rest (a common fingerprint of spliced/pasted edits) light up as suspicious. Produces an ELA suspicion score out of 100.`,
        `<strong>Frequency-Domain Noise Ratio:</strong> A DCT (Discrete Cosine Transform) frequency analysis measures the ratio of high-frequency to low-frequency components. Real camera sensors produce natural high-frequency noise; AI-generated images tend to be unnaturally smooth or show regular patterns. Produces a numeric ratio.`,
        `<strong>EXIF Metadata Inspection:</strong> The file's embedded metadata is scanned for camera make/model info (authentic photos usually have it, AI images never do) and for flagged editing software (Photoshop, GIMP, etc.).`,
        `<strong>Percentage Breakdown:</strong> The three signals above are combined into a weighted Real% / Edited% / AI-Generated% estimate, and a verdict is assigned (likely_authentic, likely_edited, likely_ai_generated, or inconclusive).`,
        `<strong>LLM Forensic Explanation:</strong> Under Gemini, the vision LLM receives both the image and the heuristic signals. Under Ollama, the text LLM receives the OCR text and heuristic signals. In both cases, the model writes a user-friendly, detailed explanation of the breakdown percentages.`,
        `<strong>Video Mode:</strong> For video files, up to 24 frames are sampled evenly across the clip. Each frame is classified independently, and the final percentages represent the proportion of frames in each category. Audio is transcribed using Faster-Whisper. The first frame is analyzed for the written explanation.`,
      ],
      output: "Real/Edited/AI-Generated percentage breakdown, verdict, ELA + frequency + metadata signals, and a detailed forensic explanation. Passed to Steps 3, 4, and 5.",
      tech: ["PIL/Pillow", "NumPy + SciPy (DCT)", "OpenCV (video sampling)", "Faster-Whisper (audio transcription)", "LLM (explanation)"],
      timeout: `${settings.pipeline_step_timeout_seconds || 120} seconds`,
      get_model: (s) => s.default_llm_provider === "gemini" ? s.gemini_model : s.ollama_vision_model
    },
    {
      num: 3,
      name: "Authenticity — Fact-Check & Source Verification",
      desc: `This step performs real-time fact-checking by searching the web and verifying claims against live sources. It uses the AI Insight from Steps 1 and 2 plus the raw image context when available to generate its search query.`,
      substeps: [
        `<strong>Search Query Generation:</strong> By default, a fast query generator uses regex/heuristics to extract key terms and URLs from the claim text. If this is disabled (via <code>STEP3_FAST_QUERY_GEN</code> in <code>.env</code>) or fails, the LLM generates a concise 3-4 word Google search query based on Step 1 & 2 outputs.`,
        `<strong>RAG Cache Lookup:</strong> The system checks its local vector store (RAG retriever) for the top 1 cached prior investigation and up to 2 official advisories (with a minimum score of 0.45) for context.`,
        `<strong>Google Web Search:</strong> The generated query is sent to the Google Custom Search API (with DuckDuckGo as a fallback), retrieving up to 3 results with titles, snippets, and URLs.`,
        `<strong>Source Scoring & Deduplication:</strong> Results are scored based on <em>Domain Trust</em> (60%) and <em>Text Similarity</em> (40%), then deduplicated by URL and Title. The top 2 ranked sources are selected.`,
        `<strong>Page Scraping (Optional):</strong> If <code>STEP3_FETCH_FULL_PAGE</code> is enabled in <code>.env</code>, the full page content of the top 2 sources is fetched in parallel using a ThreadPoolExecutor and BeautifulSoup (up to 1,500 chars). Otherwise, the search snippet is used directly.`,
        `<strong>LLM Synthesis & Verdict:</strong> The LLM receives the claim, search query, RAG matches, and source snippets/web text. It determines a verdict — <strong>likely_true</strong> (score ≥ 70), <strong>inconclusive</strong> (score 45-69), or <strong>flagged</strong> (score &lt; 45) — and writes an explanation with verified source links.`,
        `<strong>Cache Storage:</strong> The query, verdict, score, and top source URL are saved into the RAG vector store for future lookups.`,
      ],
      output: "Credibility score (0-100), verdict (likely_true / inconclusive / flagged), explanation with clickable source links, and scored source list. Passed to Steps 4 and 5.",
      tech: ["Google Custom Search API", "RAG Vector Store", "BeautifulSoup & ThreadPoolExecutor (optional scraping)", "LLM (synthesis)"],
      timeout: `${settings.pipeline_step_timeout_seconds || 120} seconds`,
      get_model: (s) => s.default_llm_provider === "gemini" ? s.gemini_model : s.ollama_model
    },
    {
      num: 4,
      name: "Actionable Items — Personalized Security Recommendations",
      desc: `This step synthesizes the combined findings from all previous steps into a focused, actionable security checklist tailored to the specific content that was analyzed.`,
      substeps: [
        `<strong>Context Distillation:</strong> Key findings are extracted: the AI Insight (Step 1, capped at 180 chars), the visual breakdown percentages from Step 2, and the fact-check verdict, score, and explanation (Step 3, capped at 180 chars).`,
        `<strong>LLM Action Generation:</strong> The LLM generates 3-5 specific, concrete actions. The recommendations are strictly tailored to the verdict: defensive measures (like blocking/reporting) for <em>flagged</em>; safe engagement and link checking for <em>likely_true</em>; and caution/further verification for <em>inconclusive</em>.`,
        `<strong>Privacy & Generality Rules:</strong> The LLM is prohibited from outputting specific usernames, handles (@username), or names of individuals/organizations, keeping recommendations general and clean.`,
      ],
      output: "A numbered list of 3-5 concrete, specific action items that the user can immediately follow.",
      tech: ["LLM (text only)"],
      timeout: `${settings.pipeline_step_timeout_seconds || 120} seconds`,
      get_model: (s) => s.default_llm_provider === "gemini" ? s.gemini_model : s.ollama_model
    },
    {
      num: 5,
      name: "Learnings — Educational Resources & Digital Literacy",
      desc: `This step turns the analysis into a learning opportunity by finding and curating relevant educational materials that teach the user how to recognize similar threats in the future.`,
      substeps: [
        `<strong>Context Distillation:</strong> The verdict, AI insight (capped at 200 chars), visual breakdown, and fact-check summary (capped at 300 chars) are combined into a compact context summary.`,
        `<strong>Educational Query Generation:</strong> The LLM generates a 3-6 word search query to find educational guides or digital literacy resources. Falls back to a generic query if generation fails.`,
        `<strong>Google Web Search:</strong> Queries Google Custom Search API for up to 3 results, prioritizing domains like <code>.gov.ph</code>, <code>.edu.ph</code>, <code>wikipedia.org</code>, and <code>factcheck.org</code>. Falls back to Step 3 sources if search results are empty.`,
        `<strong>LLM Educational Synthesis:</strong> The LLM explains the general threat pattern and how to spot it (e.g. emotional framing, clickbait) in 2-3 sentences. To prevent hallucination, the LLM is forbidden from generating URLs. The system then programmatically appends the verified educational resources as clickable markdown links.`,
      ],
      output: "A 2-3 sentence educational explanation of the threat pattern, plus programmatically appended clickable links to official educational resources.",
      tech: ["Google Custom Search API", "LLM (synthesis)"],
      timeout: `${settings.pipeline_step_timeout_seconds || 120} seconds`,
      get_model: (s) => s.default_llm_provider === "gemini" ? s.gemini_model : s.ollama_model
    }
  ];

  for (const step of steps) {
    const activeModel = typeof step.get_model === "function" ? step.get_model(settings) : "";
    const substepsHtml = (step.substeps || []).map(s =>
      `<li style="margin-bottom:6px; line-height:1.5;">${s}</li>`
    ).join("");
    const techBadges = (step.tech || []).map(t =>
      `<span style="display:inline-block; font-size:11px; padding:2px 8px; border-radius:4px; background:rgba(99,102,241,0.12); color:var(--accent); border:1px solid rgba(99,102,241,0.25); margin:2px;">${t}</span>`
    ).join(" ");

    stepinfoCards.innerHTML += `
      <div class="card" style="display:flex; flex-direction:column; gap:10px; padding:20px;">
        <!-- Header -->
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
          <strong style="font-size:16px; color:var(--accent);">Step ${step.num}: ${step.name}</strong>
          <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
            <span style="font-size:11px; color:var(--muted); background:var(--bg); padding:3px 8px; border-radius:6px; border:1px solid var(--border);">
              ⏱ Timeout: <span style="font-family:monospace; color:var(--text);">${step.timeout}</span>
            </span>
            <span style="font-size:11px; color:var(--muted); background:var(--bg); padding:3px 8px; border-radius:6px; border:1px solid var(--border);">
              🤖 Model: <span style="font-family:monospace; color:var(--text);">${activeModel}</span>
            </span>
          </div>
        </div>

        <!-- Description -->
        <div style="font-size:13px; line-height:1.5; color:var(--muted);">
          ${step.desc}
        </div>

        <!-- Sub-steps -->
        ${substepsHtml ? `
        <div style="margin-top:4px;">
          <div style="font-size:12px; font-weight:600; color:var(--text); margin-bottom:6px; text-transform:uppercase; letter-spacing:0.5px;">How it works:</div>
          <ol style="font-size:12.5px; color:var(--muted); margin:0; padding-left:20px; line-height:1.5;">
            ${substepsHtml}
          </ol>
        </div>` : ""}

        <!-- Output -->
        ${step.output ? `
        <div style="margin-top:4px; background:rgba(16,185,129,0.06); border:1px solid rgba(16,185,129,0.2); border-radius:8px; padding:10px 14px;">
          <div style="font-size:11px; font-weight:600; color:#10b981; margin-bottom:4px; text-transform:uppercase; letter-spacing:0.5px;">📤 Output</div>
          <div style="font-size:12.5px; color:var(--muted); line-height:1.4;">${step.output}</div>
        </div>` : ""}

        <!-- Tech badges -->
        ${techBadges ? `
        <div style="margin-top:2px;">
          <span style="font-size:11px; color:var(--muted); margin-right:6px;">Technologies:</span>${techBadges}
        </div>` : ""}
      </div>`;
  }
}
