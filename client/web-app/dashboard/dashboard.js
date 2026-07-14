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
        `<strong>Image input:</strong> The <em>vision-capable</em> LLM (${settings.default_llm_provider === "gemini" ? settings.gemini_model : settings.ollama_vision_model}) directly examines the image to describe what's visible — logos, text overlays, screenshots — and flags potential signs of visual tampering or AI generation.`,
        `<strong>Image + Caption (Post):</strong> Both the attached image and the accompanying caption text are passed together to the vision LLM, producing a combined summary of the full post.`,
        `<strong>Video input:</strong> The first frame of the video is extracted using OpenCV and passed to the vision LLM as a representative screenshot for analysis.`,
      ],
      output: "A concise 2-4 sentence overview/summary that is passed to Steps 3, 4, and 5 as foundational context.",
      tech: ["LLM (text or vision)", "OpenCV (video frame extraction)"],
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
        `<strong>LLM Forensic Explanation:</strong> The vision LLM receives both the image and the numeric heuristic signals, and writes a user-friendly, detailed explanation of <em>why</em> the breakdown percentages are what they are, describing visual details it can see.`,
        `<strong>Video Mode:</strong> For video files, up to 24 frames are sampled evenly across the clip. Each frame is classified independently, and the final percentages represent the proportion of frames in each category. Audio is transcribed (if available). The first frame is passed to the vision LLM for the written explanation.`,
      ],
      output: "Real/Edited/AI-Generated percentage breakdown, verdict, ELA + frequency + metadata signals, and a detailed forensic explanation. Passed to Steps 3, 4, and 5.",
      tech: ["PIL/Pillow", "NumPy + SciPy (DCT)", "OpenCV (video sampling)", "Vision LLM (explanation)"],
      timeout: `${settings.pipeline_step_timeout_seconds || 120} seconds`,
      get_model: (s) => s.default_llm_provider === "gemini" ? s.gemini_model : s.ollama_vision_model
    },
    {
      num: 3,
      name: "Authenticity — Fact-Check & Source Verification",
      desc: `This step performs real-time fact-checking by searching the web and verifying claims against live sources. It uses the AI Insight from Steps 1 and 2 plus the raw image context when available to generate its search query.`,
      substeps: [
        `<strong>Search Query Generation (LLM):</strong> The LLM reads the AI Insight from Step 1 and the Content Analyser explanation from Step 2, then generates a concise 3-6 word Google search query designed to find news, fact-checks, or official sources related to the content. Falls back to the raw claim text if generation fails.`,
        `<strong>RAG Cache Lookup:</strong> Before searching the web, the system checks its local vector store (RAG retriever) for any prior investigations on a similar query, returning the top 3 cached matches for context.`,
        `<strong>Google Web Search:</strong> The generated query is sent to the Google Custom Search API (with DuckDuckGo as a fallback). Up to 5 results are retrieved with titles, snippets, and URLs.`,
        `<strong>Source Scoring:</strong> Each search result is scored by two factors: <em>Domain Trust</em> (known credible domains like .gov, major news outlets) × 60% + <em>Text Similarity</em> (how closely the snippet matches the claim) × 40%. Results are ranked by combined score.`,
        `<strong>Parallel Page Scraping:</strong> The full webpage content of the top 4 ranked sources is fetched in parallel using a ThreadPoolExecutor. HTML is stripped to plain text (up to 1,500 chars per page) using BeautifulSoup.`,
        `<strong>LLM Synthesis & Verdict:</strong> The LLM receives the claim, the search query, cached prior investigations, and the full scraped page contents. It determines a verdict — <strong>LEGIT</strong> (likely true, score ≥ 70), <strong>QUESTIONABLE</strong> (inconclusive, score 45-69), or <strong>FAKE</strong> (likely false/flagged, score < 45) — and writes an explanation with clickable source links.`,
        `<strong>Cache Storage:</strong> The query + verdict + score are saved into the RAG vector store for future lookups, so repeated or similar claims are answered faster.`,
      ],
      output: "Credibility score (0-100), verdict (likely_true / inconclusive / flagged), explanation with clickable source links, and scored source list. Passed to Steps 4 and 5.",
      tech: ["Google Custom Search API", "BeautifulSoup (web scraping)", "RAG Vector Store", "ThreadPoolExecutor (parallel fetch)", "LLM (query gen + synthesis)"],
      timeout: `${settings.pipeline_step_timeout_seconds || 120} seconds`,
      get_model: (s) => s.default_llm_provider === "gemini" ? s.gemini_model : s.ollama_model
    },
    {
      num: 4,
      name: "Actionable Items — Personalized Security Recommendations",
      desc: `This step synthesizes the combined findings from all previous steps into a focused, actionable security checklist tailored to the specific content that was analyzed.`,
      substeps: [
        `<strong>Context Distillation:</strong> Key findings are extracted from all 3 prior steps: the AI Insight (Step 1, capped at 300 chars), the visual breakdown percentages + explanation from the Content Analyser (Step 2), and the fact-check verdict, score, and explanation (Step 3, capped at 300 chars).`,
        `<strong>LLM Action Generation:</strong> A single LLM call receives this distilled context and generates 3-5 specific, concrete action items. The actions are <em>strictly derived</em> from the findings — for example, if Step 2 detected AI-generation markers, the action will specifically warn about that; if Step 3 found no credible sources, the action will tell the user not to share the content.`,
        `<strong>Specificity Rules:</strong> The LLM is instructed to avoid generic advice. If the content is verified as authentic, it still provides one specific double-check safety rule. Every recommendation must reference a specific finding from the analysis.`,
      ],
      output: "A numbered list of 3-5 concrete, specific action items that the user can immediately follow. Displayed directly in the extension UI.",
      tech: ["LLM (text only — no vision needed)"],
      timeout: `${settings.pipeline_step_timeout_seconds || 120} seconds`,
      get_model: (s) => s.default_llm_provider === "gemini" ? s.gemini_model : s.ollama_model
    },
    {
      num: 5,
      name: "Learnings — Educational Resources & Digital Literacy",
      desc: `This step turns the analysis into a learning opportunity by finding and curating relevant educational materials that teach the user how to recognize similar threats in the future.`,
      substeps: [
        `<strong>Context Distillation:</strong> The verdict (Step 3), AI insight (Step 1), visual breakdown (Step 2), and fact-check summary (Step 3) are combined into a compact context summary describing the type of content/threat that was detected.`,
        `<strong>Educational Query Generation (LLM):</strong> The LLM generates a 3-6 word search query specifically designed to find official educational materials, guides, and articles about this type of scam or misinformation pattern. Falls back to a generic query (e.g., "flagged scam educational guide digital literacy") if generation fails.`,
        `<strong>Google Web Search:</strong> The educational query is searched using the Google Custom Search API, returning up to 4 results. Results are scored by domain trust (prioritizing government sites, official educational resources, and established digital literacy organizations).`,
        `<strong>Parallel Page Scraping:</strong> The top 3 educational sources are fetched in parallel, their HTML stripped to plain text (up to 1,000 chars per page) to give the LLM real content to work with.`,
        `<strong>LLM Educational Synthesis:</strong> The LLM reads the analysis context and the scraped educational content, then: (a) explains the general pattern behind this type of scam and why it works, (b) teaches the user how to recognize it independently next time, and (c) lists the most relevant, credible resources as clickable markdown links with descriptions of what the user will learn from each one.`,
      ],
      output: "A 2-3 sentence educational explanation of the threat pattern, plus curated clickable links to official educational resources and guides.",
      tech: ["Google Custom Search API", "BeautifulSoup (web scraping)", "ThreadPoolExecutor (parallel fetch)", "LLM (query gen + synthesis)"],
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
