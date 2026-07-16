// ---------- Global Chart References & Config ----------
let trendChartInstance = null;
let verdictChartInstance = null;
window.lastTotalScans = 0;

// Custom plugin to render centered dynamic total text inside doughnut chart
const centerTextPlugin = {
  id: 'centerText',
  afterDraw: (chart) => {
    if (chart.config.type !== 'doughnut') return;
    const { ctx } = chart;
    const meta = chart.getDatasetMeta(0);
    if (!meta || !meta.data || !meta.data[0]) return;
    
    // Sum only visible segments
    let total = 0;
    let visibleCount = 0;
    meta.data.forEach((element, index) => {
      if (chart.getDataVisibility(index)) {
        total += chart.data.datasets[0].data[index];
        visibleCount++;
      }
    });
    
    // Fallback to the saved API total scans if no segments are visible or populated
    const displayVal = visibleCount > 0 ? total : (window.lastTotalScans || 0);
    
    const x = meta.data[0].x;
    const y = meta.data[0].y;
    
    ctx.save();
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    
    // Draw Value
    ctx.font = 'bold 24px "Space Grotesk", sans-serif';
    ctx.fillStyle = '#f3f4f6';
    ctx.fillText(displayVal.toString(), x, y - 8);
    
    // Draw Label
    ctx.font = '600 9px "Inter", sans-serif';
    ctx.fillStyle = '#9ca3af';
    ctx.fillText('SCANS', x, y + 12);
    
    ctx.restore();
  }
};

// ---------- Tab Switcher ----------
document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll("main > section").forEach(s => s.style.display = "none");
    btn.classList.add("active");
    
    const targetSection = document.getElementById(`tab-${btn.dataset.tab}`);
    if (targetSection) {
      targetSection.style.display = "block";
    }
    
    if (btn.dataset.tab === "stepinfo") {
      loadStepInfo();
    }
  });
});

// ---------- Settings & Global Configuration ----------
let pipelineTimeoutSeconds = 120;
let maxReferenceDocSizeMb = 10;
let supportedLanguages = {
  ollama: ["english"],
  gemini: ["english", "taglish", "tagalog", "cebuano", "bisaya", "ilocano"],
};

async function loadSettings() {
  try {
    const settings = await ApiClient.getSettings();
    if (settings?.pipeline_step_timeout_seconds) {
      pipelineTimeoutSeconds = Number(settings.pipeline_step_timeout_seconds) || pipelineTimeoutSeconds;
    }
    if (settings?.max_reference_doc_size_mb) {
      maxReferenceDocSizeMb = Number(settings.max_reference_doc_size_mb) || maxReferenceDocSizeMb;
      const hint = document.getElementById("refdoc-max-size-hint");
      if (hint) {
        hint.textContent = `Maximum file size: ${maxReferenceDocSizeMb} MB`;
      }
    }
    if (settings?.supported_languages) {
      supportedLanguages = settings.supported_languages;
    }
    if (settings?.default_llm_provider) {
      document.getElementById("llm-provider").value = settings.default_llm_provider;
    }
    if (settings?.tts_enabled !== undefined) {
      document.getElementById("tts-toggle").checked = settings.tts_enabled;
      window.ttsPlayer.setEnabled(settings.tts_enabled);
      populateVoiceDropdown();
      updateVoiceControlsVisibility();
    }
    updateLanguageOptions();

function updateVoiceControlsVisibility() {
  const enabled = ttsToggle.checked;
  if (ttsVoice) ttsVoice.style.display = enabled ? "inline-block" : "none";
  
  let hasCompletedSpeech = false;
  for (let i = 1; i <= 5; i++) {
    const row = document.getElementById(`step-${i}`);
    if (row && row.dataset.speechText) {
      hasCompletedSpeech = true;
      break;
    }
  }
  if (ttsReplay) ttsReplay.style.display = (enabled && hasCompletedSpeech) ? "inline-block" : "none";
}

function populateVoiceDropdown() {
  if (!ttsVoice) return;
  ttsVoice.innerHTML = "";
  const voices = window.ttsPlayer.voices || [];
  for (const voice of voices) {
    const opt = document.createElement("option");
    opt.value = voice.name;
    opt.textContent = `${voice.name} (${voice.lang})`;
    ttsVoice.appendChild(opt);
  }
  if (window.ttsPlayer.selectedVoiceName) {
    ttsVoice.value = window.ttsPlayer.selectedVoiceName;
  }
}
  } catch (err) {
    console.warn("Unable to load settings:", err);
  }
}

// ---------- Overview Stats & Visual Charts ----------
async function loadOverview() {
  try {
    const summary = await ApiClient.getSummary();
    
    // Calculate custom metrics from summary verdict counts
    const verdicts = summary.by_verdict || {};
    const safeCount = (verdicts.likely_true || 0) + (verdicts.likely_authentic || 0);
    const warnCount = verdicts.inconclusive || 0;
    const badCount = (verdicts.flagged || 0) + (verdicts.likely_edited || 0) + (verdicts.likely_ai_generated || 0);

    // Update Top Stat Cards with count values
    document.getElementById("val-total-scans").textContent = summary.total_scans || 0;
    document.getElementById("val-safe-scans").textContent = safeCount;
    document.getElementById("val-warn-scans").textContent = warnCount;
    document.getElementById("val-bad-scans").textContent = badCount;
    window.lastTotalScans = summary.total_scans || 0;

    // Load Trend Stats
    const trend = await ApiClient.getTrends(30);
    const days = [...new Set(trend.map(t => t.day))].sort();
    const channels = [...new Set(trend.map(t => t.channel))];
    
    // Core visual palette
    const colors = { extension: "#6366f1", messenger: "#10b981", webapp: "#f59e0b" };
    const chartColorsGlow = {
      extension: "rgba(99, 102, 241, 0.15)",
      messenger: "rgba(16, 185, 129, 0.15)",
      webapp: "rgba(245, 158, 11, 0.15)"
    };

    if (typeof Chart === "undefined") {
      throw new ReferenceError("Chart.js library is not loaded.");
    }

    // 1. Scans Over Time - Line Chart
    const trendCtx = document.getElementById("trend-chart").getContext("2d");
    
    if (trendChartInstance) {
      trendChartInstance.destroy();
    }

    const datasets = channels.map(c => {
      // Create glowing gradient fills
      const gradient = trendCtx.createLinearGradient(0, 0, 0, 240);
      gradient.addColorStop(0, chartColorsGlow[c] || "rgba(156, 163, 175, 0.15)");
      gradient.addColorStop(1, "rgba(9, 10, 15, 0.0)");

      return {
        label: c.toUpperCase(),
        data: days.map(d => (trend.find(t => t.day === d && t.channel === c) || {}).c || 0),
        borderColor: colors[c] || "#9ca3af",
        backgroundColor: gradient,
        fill: true,
        tension: 0.4,
        borderWidth: 2,
        pointBackgroundColor: colors[c] || "#9ca3af",
        pointBorderColor: "rgba(255, 255, 255, 0.1)",
        pointHoverRadius: 6,
        pointRadius: 3
      };
    });

    trendChartInstance = new Chart(document.getElementById("trend-chart"), {
      type: "line",
      data: {
        labels: days.map(d => {
          // Format "YYYY-MM-DD" to short date "MMM DD"
          const dateObj = new Date(d);
          return isNaN(dateObj.getTime()) ? d : dateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        }),
        datasets: datasets,
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        resizeDelay: 0,
        plugins: {
          legend: {
            display: true,
            position: 'top',
            labels: {
              color: "#9ca3af",
              font: { family: "Inter", size: window.innerWidth < 550 ? 9 : 11, weight: 500 },
              boxWidth: 8,
              boxHeight: 8,
              usePointStyle: true,
              pointStyle: 'circle'
            }
          },
          tooltip: {
            backgroundColor: "#11131e",
            borderColor: "rgba(255, 255, 255, 0.08)",
            borderWidth: 1,
            titleColor: "#f3f4f6",
            bodyColor: "#9ca3af",
            titleFont: { family: "Inter", weight: 600, size: window.innerWidth < 550 ? 10 : 12 },
            bodyFont: { family: "Inter", size: window.innerWidth < 550 ? 9 : 11 },
            padding: 10,
            cornerRadius: 8
          }
        },
        scales: {
          x: {
            grid: { color: "rgba(255, 255, 255, 0.03)", drawBorder: false },
            ticks: { 
              color: "#9ca3af", 
              font: { family: "Inter", size: window.innerWidth < 550 ? 8 : 10 },
              maxRotation: 45,
              minRotation: 0
            }
          },
          y: {
            grid: { color: "rgba(255, 255, 255, 0.03)", drawBorder: false },
            ticks: { 
              color: "#9ca3af", 
              font: { family: "Inter", size: window.innerWidth < 550 ? 8 : 10 }, 
              precision: 0 
            }
          }
        }
      },
    });

    // 2. Verdicts Distribution - Doughnut Chart
    if (verdictChartInstance) {
      verdictChartInstance.destroy();
    }

    const verdictKeys = Object.keys(verdicts);
    const verdictVals = Object.values(verdicts);

    const verdictColors = {
      likely_true: "#10b981",
      likely_authentic: "#10b981",
      inconclusive: "#f59e0b",
      flagged: "#ef4444",
      likely_ai_generated: "#ef4444",
      likely_edited: "#ef4444"
    };

    const bgColors = verdictKeys.map(k => verdictColors[k] || "#4f46e5");

    verdictChartInstance = new Chart(document.getElementById("verdict-chart"), {
      type: "doughnut",
      data: {
        labels: verdictKeys.map(k => k.replace(/_/g, " ").toUpperCase()),
        datasets: [{
          data: verdictVals,
          backgroundColor: bgColors,
          borderWidth: 0,
          hoverOffset: 4
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        resizeDelay: 0,
        cutout: "76%",
        plugins: {
          legend: {
            display: true,
            position: window.innerWidth < 650 ? 'bottom' : 'right',
            labels: {
              color: "#9ca3af",
              font: { family: "Inter", size: window.innerWidth < 550 ? 9 : 10, weight: 500 },
              boxWidth: 8,
              boxHeight: 8,
              usePointStyle: true,
              pointStyle: 'circle',
              padding: window.innerWidth < 550 ? 6 : 10
            }
          },
          tooltip: {
            backgroundColor: "#11131e",
            borderColor: "rgba(255, 255, 255, 0.08)",
            borderWidth: 1,
            titleColor: "#f3f4f6",
            bodyColor: "#9ca3af",
            padding: 10,
            cornerRadius: 8
          }
        },
      },
      plugins: [centerTextPlugin]
    });

  } catch (err) {
    console.error("Dashboard visualization error:", err);
    document.getElementById("trend-chart").parentElement.innerHTML = `<div style="padding:40px; text-align:center; color:var(--muted)">Visualization unavailable: ${err.message}</div>`;
    document.getElementById("verdict-chart").parentElement.innerHTML = `<div style="padding:40px; text-align:center; color:var(--muted)">Verdict distribution unavailable: ${err.message}</div>`;
  }
}

// ---------- Scan History Table & Filters ----------
async function loadScans() {
  const channel = document.getElementById("filter-channel").value;
  const limit = document.getElementById("limit-scans").value;
  const searchQuery = document.getElementById("search-scans").value.toLowerCase();
  
  // Fetch slightly more to filter client side if searching
  const fetchLimit = searchQuery ? 100 : Number(limit);
  const scans = await ApiClient.getScans({ channel, limit: fetchLimit });
  const tbody = document.querySelector("#scans-table tbody");
  tbody.innerHTML = "";

  // Apply search query locally
  const filteredScans = scans.filter(s => {
    if (!searchQuery) return true;
    const summary = (s.input_summary || "").toLowerCase();
    const verdict = (s.step3_verdict || "").toLowerCase();
    const type = (s.content_type || "").toLowerCase();
    return summary.includes(searchQuery) || verdict.includes(searchQuery) || type.includes(searchQuery);
  });

  // Limit display to set limit
  const displayScans = filteredScans.slice(0, Number(limit));

  if (displayScans.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding: 40px; color: var(--muted-light);">No scans matching current filters.</td></tr>`;
    return;
  }

  for (const s of displayScans) {
    const tr = document.createElement("tr");
    const scoreVal = s.step2_score !== null && s.step2_score !== undefined ? s.step2_score : "—";
    
    tr.innerHTML = `
      <td>${new Date(s.created_at + "Z").toLocaleString()}</td>
      <td><span style="font-weight: 500; font-size:12px;">${s.channel.toUpperCase()}</span></td>
      <td><span style="color: var(--muted-light);">${s.content_type ?? "—"}</span></td>
      <td style="max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${s.input_summary || "—"}</td>
      <td><strong style="color: ${scoreVal !== "—" ? 'var(--accent-light)' : 'inherit'};">${scoreVal}</strong></td>
      <td><span class="badge ${s.step3_verdict}">${(s.step3_verdict || "—").replace(/_/g, " ")}</span></td>`;
    
    tr.addEventListener("click", () => openModal(s.raw_result_json));
    tbody.appendChild(tr);
  }
}

// Bind Filter Event Listeners
document.getElementById("refresh-scans").addEventListener("click", loadScans);
document.getElementById("filter-channel").addEventListener("change", loadScans);
document.getElementById("limit-scans").addEventListener("change", loadScans);
document.getElementById("search-scans").addEventListener("input", loadScans);

document.getElementById("clear-scans").addEventListener("click", async () => {
  if (confirm("Are you sure you want to clear all scan history? This will also clear the local RAG database cache.")) {
    await ApiClient.clearScans();
    loadScans();
    loadOverview();
  }
});

// ---------- JSON Result Detail Modal ----------
function openModal(rawJson) {
  try {
    document.getElementById("modal-body").textContent = JSON.stringify(JSON.parse(rawJson), null, 2);
  } catch (e) {
    document.getElementById("modal-body").textContent = rawJson;
  }
  document.getElementById("detail-modal").classList.add("open");
}

document.getElementById("modal-close").addEventListener("click", () => {
  document.getElementById("detail-modal").classList.remove("open");
});

// ---------- Reference Documents ----------
async function loadRefDocs() {
  const docs = await ApiClient.getReferenceDocuments();
  const grid = document.getElementById("refdoc-grid");
  grid.innerHTML = "";
  
  if (docs.length === 0) {
    grid.innerHTML = `<div style="grid-column: 1/-1; padding: 40px; text-align: center; color: var(--muted-light); border: 1px dashed var(--border); border-radius: 12px;">No reference documents uploaded yet. Upload one above to train the local RAG database.</div>`;
    return;
  }

  for (const d of docs) {
    // Show image preview if available
    let imgHtml = "";
    if (d.image_path) {
      imgHtml = `<img src="/api/reference-documents/image/${d.id}" alt="${d.name}" onerror="this.src='https://placehold.co/200x120/11131e/9ca3af?text=No+Preview'">`;
    }
    grid.innerHTML += `
      <div class="ref-card">
        <span class="del" data-id="${d.id}">✕</span>
        ${imgHtml}
        <div style="font-weight:600; font-size:13px; color:var(--text);">${d.name}</div>
        <div style="font-size:11px; color:var(--accent-light); font-weight:600; text-transform:uppercase; margin-top:2px;">${d.category}</div>
        ${d.notes ? `<div style="color:var(--muted); font-size:11px; margin-top:4px; font-style:italic;">${d.notes}</div>` : ""}
        <div style="color:var(--muted-light); font-size:10px; margin-top:6px; border-t: 1px solid var(--border); padding-top:4px;">Uploaded ${new Date(d.uploaded_at + "Z").toLocaleDateString()}</div>
      </div>`;
  }
  
  grid.querySelectorAll(".del").forEach(el => {
    el.addEventListener("click", async () => {
      if (confirm(`Delete reference document?`)) {
        await ApiClient.deleteReferenceDocument(el.dataset.id);
        loadRefDocs();
      }
    });
  });
}

function onRefDocFileSelected(input) {
  const file = input.files[0];
  const label = document.getElementById('refdoc-file-label');
  if (!file) {
    if (label) label.textContent = 'No file selected';
    return;
  }
  
  // Validate file size limit client-side
  const maxBytes = maxReferenceDocSizeMb * 1024 * 1024;
  if (file.size > maxBytes) {
    alert(`The selected image exceeds the maximum allowed file size of ${maxReferenceDocSizeMb} MB. Please upload a smaller image.`);
    input.value = ""; // Clear file
    if (label) label.textContent = 'No file selected';
    return;
  }
  
  if (label) label.textContent = file.name;
}

document.getElementById("refdoc-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const fileInput = document.getElementById("refdoc-file-input");
  const file = fileInput.files[0];
  
  if (!file) {
    alert("Please select a file to upload.");
    return;
  }
  
  // Extra safety validation before submission
  const maxBytes = maxReferenceDocSizeMb * 1024 * 1024;
  if (file.size > maxBytes) {
    alert(`The selected image exceeds the maximum allowed file size of ${maxReferenceDocSizeMb} MB. Please upload a smaller image.`);
    fileInput.value = "";
    document.getElementById('refdoc-file-label').textContent = 'No file selected';
    return;
  }

  try {
    await ApiClient.uploadReferenceDocument(new FormData(form));
    form.reset();
    document.getElementById('refdoc-file-label').textContent = 'No file selected';
    loadRefDocs();
  } catch (err) {
    console.error("Upload reference document failed:", err);
    alert(err.message || "Failed to upload reference document.");
  }
});

// ---------- Error Logs ----------
async function loadErrors() {
  const errors = await ApiClient.getErrors(100);
  const tbody = document.querySelector("#errors-table tbody");
  tbody.innerHTML = "";
  document.getElementById("error-count").textContent = `${errors.length} error(s) logged`;

  if (errors.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4" style="text-align:center; padding: 40px; color: var(--muted-light);">No pipeline errors logged.</td></tr>`;
    return;
  }

  for (const err of errors) {
    const tr = document.createElement("tr");
    const stepLabel = err.step_name
      ? `Step ${err.step} — ${err.step_name}`
      : (err.error_type === "system" ? "System" : "General");
    const shortMsg = err.error_msg.length > 120 ? err.error_msg.slice(0, 120) + "…" : err.error_msg;
    
    tr.innerHTML = `
      <td>${new Date(err.created_at + "Z").toLocaleString()}</td>
      <td><span style="font-weight: 500;">${stepLabel}</span></td>
      <td><span class="badge ${err.error_type === "system" ? "flagged" : "inconclusive"}">${err.error_type}</span></td>
      <td style="font-family:monospace; font-size:12px; color: var(--bad);">${shortMsg}</td>`;
    
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


// ---------- Step Info Module (Preserved Functionality & Layout) ----------
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
      <div class="card" style="display:flex; flex-direction:column; gap:10px; padding:20px; border-left: 4px solid var(--accent);">
        <!-- Header -->
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
          <strong style="font-size:16px; color:var(--accent-light);">Step ${step.num}: ${step.name}</strong>
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


// ---------- NEW ANALYZE MODAL SYSTEM ----------
const STEP_LABELS = {
  1: "(Step 1) AI Insights", 2: "(Step 2) Content Analyser", 3: "(Step 3) Authenticity",
  4: "(Step 4) Actionable Items", 5: "(Step 5) Learnings",
};

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

const openAnalyzeBtn = document.getElementById("header-analyze-btn");
const analyzeModal = document.getElementById("analyze-modal");
const analyzeModalClose = document.getElementById("analyze-modal-close");
const inputStage = document.getElementById("analyze-input-stage");
const progressStage = document.getElementById("analyze-progress-stage");
const modeSelect = document.getElementById("content-mode");
const textInput = document.getElementById("text-input");
const fileInput = document.getElementById("file-input");
const providerSelect = document.getElementById("llm-provider");
const languageSelect = document.getElementById("language");
const ttsToggle = document.getElementById("tts-toggle");
const ttsVoice = document.getElementById("tts-voice");
const ttsReplay = document.getElementById("tts-replay");
const ocrToggle = document.getElementById("ocr-toggle");
const dropZone = document.getElementById("drop-zone");
const previewContainer = document.getElementById("file-preview-container");
const previewImg = document.getElementById("file-preview-img");
const removePreviewBtn = document.getElementById("remove-preview-btn");
const analyzeForm = document.getElementById("analyze-form");
const submitBtn = document.getElementById("submit-btn");
const doneBtn = document.getElementById("analysis-done-btn");
const cancelVoiceBtn = document.getElementById("cancel-voice-btn");
const progressLine = document.getElementById("pipeline-progress-line");
const errorBanner = document.getElementById("error-banner");
const pipelineSpinner = document.getElementById("pipeline-spinner");

function openAnalyzeModal() {
  analyzeModal.classList.add("open");
  resetAnalyzeModal();
}

function closeAnalyzeModal() {
  analyzeModal.classList.remove("open");
  window.ttsPlayer.stop();
  // Refresh stats in case we completed runs
  loadOverview();
  loadScans();
  loadErrors();
}

openAnalyzeBtn.addEventListener("click", openAnalyzeModal);
analyzeModalClose.addEventListener("click", closeAnalyzeModal);
doneBtn.addEventListener("click", closeAnalyzeModal);

cancelVoiceBtn.addEventListener("click", () => {
  window.ttsPlayer.stop();
  cancelVoiceBtn.style.display = "none";
});

// Dropzone click -> file select
dropZone.addEventListener("click", () => fileInput.click());

// Drag events
dropZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropZone.classList.add("dragover");
});

dropZone.addEventListener("dragleave", () => {
  dropZone.classList.remove("dragover");
});

dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZone.classList.remove("dragover");
  if (e.dataTransfer.files.length > 0) {
    fileInput.files = e.dataTransfer.files;
    handleFileSelected(fileInput.files[0]);
  }
});

fileInput.addEventListener("change", () => {
  if (fileInput.files.length > 0) {
    handleFileSelected(fileInput.files[0]);
  }
});

removePreviewBtn.addEventListener("click", () => {
  clearFileSelection();
});

function handleFileSelected(file) {
  if (!file) return;
  
  if (file.type.startsWith("image/")) {
    const reader = new FileReader();
    reader.onload = (e) => {
      previewImg.src = e.target.result;
      previewContainer.style.display = "flex";
      dropZone.style.display = "none";
    };
    reader.readAsDataURL(file);
  } else if (file.type.startsWith("video/")) {
    // Standard video icon for previews
    previewImg.src = "https://placehold.co/200x120/11131e/9ca3af?text=Video+Selected";
    previewContainer.style.display = "flex";
    dropZone.style.display = "none";
  }
}

function clearFileSelection() {
  fileInput.value = "";
  previewImg.src = "";
  previewContainer.style.display = "none";
  // Restore drop zone if file/post mode is active
  const mode = modeSelect.value;
  if (mode === "image" || mode === "video" || mode === "post") {
    dropZone.style.display = "flex";
  }
}

function resetAnalyzeModal() {
  inputStage.style.display = "block";
  progressStage.style.display = "none";
  doneBtn.style.display = "none";
  cancelVoiceBtn.style.display = "none";
  errorBanner.style.display = "none";
  errorBanner.textContent = "";
  pipelineSpinner.style.display = "block";
  submitBtn.disabled = false;
  
  textInput.value = "";
  clearFileSelection();
  updateFormFields();

  // Clear speech states
  window.ttsPlayer.stop();
  for (let i = 1; i <= 5; i++) {
    const row = document.getElementById(`step-${i}`);
    if (row) {
      delete row.dataset.speechText;
    }
  }
  updateVoiceControlsVisibility();
}

function updateLanguageOptions() {
  const provider = providerSelect.value || "gemini";
  const allowed = supportedLanguages[provider] || supportedLanguages.gemini;
  const currentValue = languageSelect.value;

  languageSelect.innerHTML = "";
  for (const lang of allowed) {
    const option = document.createElement("option");
    option.value = lang;
    option.textContent = lang.charAt(0).toUpperCase() + lang.slice(1);
    languageSelect.appendChild(option);
  }

  if (allowed.includes(currentValue)) {
    languageSelect.value = currentValue;
  } else {
    languageSelect.value = "english";
  }
}

providerSelect.addEventListener("change", updateLanguageOptions);

function updateFormFields() {
  const mode = modeSelect.value;
  textInput.style.display = (mode === "text" || mode === "post") ? "block" : "none";
  dropZone.style.display = (mode === "image" || mode === "video" || mode === "post") ? "flex" : "none";
  
  if (mode === "video") {
    fileInput.accept = "video/*";
    dropZone.querySelector(".desc").textContent = "or click to upload (Video)";
  } else {
    fileInput.accept = "image/*";
    dropZone.querySelector(".desc").textContent = "or click to upload (Image)";
  }
  
  textInput.placeholder = mode === "post"
    ? "Paste the post's caption..."
    : "Paste the claim or message to check...";

  clearFileSelection();
}

modeSelect.addEventListener("change", updateFormFields);

ttsToggle.addEventListener("change", (e) => {
  window.ttsPlayer.setEnabled(e.target.checked);
  updateVoiceControlsVisibility();
});

ttsVoice.addEventListener("change", (e) => {
  window.ttsPlayer.selectedVoiceName = e.target.value;
});

ttsReplay.addEventListener("click", () => {
  window.ttsPlayer.stop();
  for (let i = 1; i <= 5; i++) {
    const row = document.getElementById(`step-${i}`);
    if (row && row.dataset.speechText) {
      window.ttsPlayer.speak(row.dataset.speechText);
    }
  }
});

// ---------- Multi-Step Execution State Managers ----------
const activeTimers = {};

function clearTimerForStep(step) {
  if (activeTimers[step]) {
    clearInterval(activeTimers[step]);
    delete activeTimers[step];
  }
}

function setStepRowStatus(step, status, iconText, bodyHtml, color) {
  const row = document.getElementById(`step-${step}`);
  if (!row) return;
  const icon = row.querySelector(".step-icon");
  const body = row.querySelector(".step-body");
  
  row.dataset.status = status;
  icon.textContent = iconText;
  
  if (color) {
    icon.style.color = color;
    row.style.color = color;
    body.style.color = color;
  } else {
    icon.style.color = "";
    row.style.color = "";
    body.style.color = "";
  }
  body.innerHTML = bodyHtml;
}

function updatePipelineNode(step, status) {
  const node = document.getElementById(`node-${step}`);
  if (!node) return;
  node.className = "pipeline-node " + status;
  
  // Set progress bar line width
  let pct = 0;
  if (status === "active") {
    pct = (step - 1) * 20 + 10;
  } else if (status === "completed") {
    pct = step * 20;
  } else if (status === "error") {
    pct = (step - 1) * 20 + 10;
  }
  if (progressLine) {
    progressLine.style.width = `${pct}%`;
  }
}

function markFollowingStepsFailed(startStep) {
  for (let step = startStep; step <= 5; step++) {
    const row = document.getElementById(`step-${step}`);
    if (!row || (row.dataset.status !== "pending" && row.dataset.status !== "in_progress")) continue;
    clearTimerForStep(step);
    setStepRowStatus(step, "error", "⚠️", formatContent("Skipped because a previous step failed."), "var(--bad)");
    updatePipelineNode(step, "error");
  }
}

function initStepRows() {
  inputStage.style.display = "none";
  progressStage.style.display = "block";
  document.getElementById("results-header").textContent = "Analyzing…";
  errorBanner.style.display = "none";
  errorBanner.textContent = "";
  
  if (progressLine) progressLine.style.width = "0%";

  for (let step = 1; step <= 5; step++) {
    clearTimerForStep(step);
    
    // Reset visual pipeline nodes
    const node = document.getElementById(`node-${step}`);
    if (node) node.className = "pipeline-node";
    
    const row = document.getElementById(`step-${step}`);
    row.dataset.status = "pending";
    row.style.cssText = `padding:12px; margin-bottom:10px;`;
    row.innerHTML = `<div style="display:flex; gap:12px; align-items:flex-start;">
      <span class="step-icon" style="flex-shrink:0; font-size:16px;">⏳</span>
      <div style="flex:1;">
        <div style="font-weight:600; font-size:13.5px; color:var(--text);">${STEP_LABELS[step]}</div>
        <div class="step-body" style="color:var(--muted); margin-top:4px; font-size:12.5px; white-space:pre-wrap;">Waiting…</div>
      </div></div>`;
  }
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
    return `<a href="${url}" target="_blank" style="color:var(--accent-light); text-decoration:underline; word-break:break-all;">${linkText}</a>`;
  });

  escaped = escaped.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  return escaped.replace(/\n/g, "<br>");
}

function updateStepRow(event) {
  const row = document.getElementById(`step-${event.step}`);
  if (!row) return;
  const icon = row.querySelector(".step-icon");
  const body = row.querySelector(".step-body");

  clearTimerForStep(event.step);

  if (event.status === "in_progress") {
    icon.textContent = "🔄";
    icon.style.color = "var(--accent-light)";
    row.style.color = "";
    body.style.color = "var(--muted)";
    row.dataset.status = "in_progress";
    updatePipelineNode(event.step, "active");
    
    let secondsLeft = pipelineTimeoutSeconds;
    body.textContent = `Working… (${secondsLeft}s remaining)`;
    
    // Narrate step start
    const lang = languageSelect.value;
    const startMsgs = STEP_START_MESSAGES[lang] || STEP_START_MESSAGES.english;
    const startMsg = startMsgs[event.step] || `Starting step ${event.step}`;
    window.ttsPlayer.speak(startMsg);

    activeTimers[event.step] = setInterval(() => {
      secondsLeft--;
      if (secondsLeft <= 0) {
        clearTimerForStep(event.step);
        if (row.dataset.status === "in_progress") {
          setStepRowStatus(event.step, "error", "⚠️", formatContent(`Step timed out after ${pipelineTimeoutSeconds} seconds.`), "var(--bad)");
          updatePipelineNode(event.step, "error");
          markFollowingStepsFailed(event.step + 1);
        }
      } else {
        body.textContent = `Working… (${secondsLeft}s remaining)`;
      }
    }, 1000);
  } else if (event.status === "error") {
    icon.textContent = "⚠️";
    icon.style.color = "var(--bad)";
    row.style.color = "var(--bad)";
    body.style.color = "var(--bad)";
    row.dataset.status = "error";
    updatePipelineNode(event.step, "error");
    body.innerHTML = formatContent(event.result?.error || "Something went wrong on this step.");
    markFollowingStepsFailed(event.step + 1);

    // Narrate step failure
    window.ttsPlayer.speak(`Step ${event.step} failed. ${event.result?.error || ""}`);
  } else if (event.status === "completed") {
    icon.textContent = "✅";
    icon.style.color = "var(--good)";
    row.style.color = "";
    body.style.color = "";
    row.dataset.status = "completed";
    updatePipelineNode(event.step, "completed");
    body.innerHTML = formatContent(summarizeStep(event.step, event.result));

    // Narrate step output
    const lang = languageSelect.value;
    window.ttsPlayer.setLanguage(lang);
    let speechText = summarizeStep(event.step, event.result);
    if (event.step === 2 && event.result.applicable !== false) {
      speechText = `Visual analysis breakdown: ${event.result.real_pct}% real, ${event.result.edited_pct}% edited, and ${event.result.ai_generated_pct}% AI-generated. ${event.result.explanation}`;
    } else if (event.step === 3) {
      speechText = `Verdict: ${event.result.verdict}. Credibility score: ${event.result.score} out of 100. ${event.result.explanation}`;
    } else if (event.step === 4) {
      speechText = `Here are the actionable items: ${(event.result.actions || []).join(". ")}`;
    }
    row.dataset.speechText = speechText;
    updateVoiceControlsVisibility();
    window.ttsPlayer.speak(speechText);
    
    if (ttsToggle.checked) {
      cancelVoiceBtn.style.display = "inline-flex";
    }
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
  if (step === 5) {
    return result.learning_material || "No learnings generated.";
  }
  return "Done.";
}

// Resizing logic for Image uploads in client browser
async function resizeImageFile(file, maxDim = 1024, quality = 0.75) {
  return new Promise((resolve, reject) => {
    try {
      const img = new Image();
      const url = URL.createObjectURL(file);
      img.onload = () => {
        try {
          let { width, height } = img;
          const maxSide = Math.max(width, height);
          let scale = 1;
          if (maxSide > maxDim) scale = maxDim / maxSide;
          if (scale >= 1) {
            URL.revokeObjectURL(url);
            resolve(file);
            return;
          }

          const canvas = document.createElement('canvas');
          canvas.width = Math.round(width * scale);
          canvas.height = Math.round(height * scale);
          const ctx = canvas.getContext('2d');
          ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

          canvas.toBlob((blob) => {
            URL.revokeObjectURL(url);
            if (!blob) return reject(new Error('Image compression failed'));
            resolve(new File([blob], file.name, { type: 'image/jpeg' }));
          }, 'image/jpeg', quality);
        } catch (err) {
          URL.revokeObjectURL(url);
          reject(err);
        }
      };
      img.onerror = (e) => {
        URL.revokeObjectURL(url);
        reject(e || new Error('Image load error'));
      };
      img.src = url;
    } catch (err) {
      reject(err);
    }
  });
}

// Submit and streaming
analyzeForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  submitBtn.disabled = true;
  initStepRows();

  const mode = modeSelect.value;
  const language = languageSelect.value;
  
  // Set language and stop previous speech
  window.ttsPlayer.setLanguage(language);
  window.ttsPlayer.stop();

  const provider = providerSelect.value || "ollama";
  const useOcr = ocrToggle ? ocrToggle.checked : true;
  const formData = new FormData();
  formData.append("language", language);
  formData.append("provider", provider);
  formData.append("use_ocr", useOcr.toString());
  formData.append("source_url", location.href);

  if (mode === "text") {
    formData.append("text", textInput.value);
  } else if (mode === "image" || mode === "video") {
    if (!fileInput.files[0]) { submitBtn.disabled = false; resetAnalyzeModal(); return; }
    const file = fileInput.files[0];
    if (file.type && file.type.startsWith("image/")) {
      try {
        const resized = await resizeImageFile(file, 1024, 0.75);
        formData.append("file", resized, file.name);
      } catch (err) {
        formData.append("file", file);
      }
    } else {
      formData.append("file", file);
    }
  } else if (mode === "post") {
    formData.append("caption", textInput.value);
    if (fileInput.files[0]) {
      const file = fileInput.files[0];
      if (file.type && file.type.startsWith("image/")) {
        try {
          const resized = await resizeImageFile(file, 1024, 0.75);
          formData.append("file", resized, file.name);
        } catch (err) {
          formData.append("file", file);
        }
      } else {
        formData.append("file", file);
      }
    }
  }

  try {
    await streamAnalyze(formData, (event) => {
      if (event.done) {
        document.getElementById("results-header").textContent = `Done — scan #${event.scan_id}`;
        pipelineSpinner.style.display = "none";
        doneBtn.style.display = "inline-flex";
        
        // Dynamic dashboard reload when done!
        loadOverview();
        loadScans();
        loadErrors();
        return;
      }
      if (event.systemError) {
        document.getElementById("results-header").textContent = "Error in System Pipeline";
        pipelineSpinner.style.display = "none";
        
        errorBanner.style.display = "block";
        errorBanner.textContent = "⚠️ System Error: " + event.systemError;
        
        doneBtn.style.display = "inline-flex";
        
        // Refresh dashboard on partial runs
        loadOverview();
        loadScans();
        loadErrors();
        return;
      }
      updateStepRow(event);
    });
  } catch (err) {
    document.getElementById("results-header").textContent = `Critical Error`;
    pipelineSpinner.style.display = "none";
    errorBanner.style.display = "block";
    errorBanner.textContent = "⚠️ " + err.message;
    doneBtn.style.display = "inline-flex";
    
    loadOverview();
    loadScans();
    loadErrors();
  } finally {
    submitBtn.disabled = false;
  }
});

// Auto-trigger analyze modal if parameters are set (SPA integration)
const urlParams = new URLSearchParams(window.location.search);
if (urlParams.get("analyze") === "true") {
  openAnalyzeModal();
  // Clear parameter from address bar
  window.history.replaceState({}, document.title, window.location.pathname);
}


// ---------- INITIALIZATION ----------
loadSettings();
loadOverview();
loadScans();
loadRefDocs();
loadErrors();
initOllamaModelSelector();

// Dynamic Window Resize Listener to adapt chart parameters instantly and smoothly
window.addEventListener('resize', () => {
  const isMobile = window.innerWidth < 550;
  const isTablet = window.innerWidth < 650;
  
  if (trendChartInstance) {
    trendChartInstance.options.plugins.legend.labels.font.size = isMobile ? 9 : 11;
    trendChartInstance.options.scales.x.ticks.font.size = isMobile ? 8 : 10;
    trendChartInstance.options.scales.y.ticks.font.size = isMobile ? 8 : 10;
    trendChartInstance.update('none'); // Update without animation for responsive performance
  }
  
  if (verdictChartInstance) {
    verdictChartInstance.options.plugins.legend.position = isTablet ? 'bottom' : 'right';
    verdictChartInstance.options.plugins.legend.labels.font.size = isMobile ? 9 : 10;
    verdictChartInstance.options.plugins.legend.labels.padding = isMobile ? 6 : 10;
    verdictChartInstance.update('none');
  }
});

// ---------- Ollama Model Selector Logic ----------
let allOllamaModels = [];
let activeOllamaModel = "";
let activeVisionModel = "";

async function initOllamaModelSelector() {
  const container = document.getElementById("ollama-selector-container");
  const trigger = document.getElementById("model-trigger");
  const dropdown = document.getElementById("model-dropdown");
  const searchInput = document.getElementById("model-search");
  const listContainer = document.getElementById("model-list");
  const activeNameSpan = document.getElementById("active-model-name");
  const overlay = document.getElementById("model-switch-overlay");
  const statusIndicator = container?.querySelector(".model-status-indicator");

  if (!trigger || !dropdown || !searchInput || !listContainer) return;

  // Toggle dropdown on click
  trigger.addEventListener("click", (e) => {
    e.stopPropagation();
    const isOpen = trigger.classList.toggle("open");
    dropdown.classList.toggle("visible");
    trigger.setAttribute("aria-expanded", isOpen);
    if (isOpen) {
      searchInput.focus();
      searchInput.value = "";
      renderModelList("");
    }
  });

  // Close dropdown on outside click
  document.addEventListener("click", (e) => {
    if (!container.contains(e.target)) {
      trigger.classList.remove("open");
      dropdown.classList.remove("visible");
      trigger.setAttribute("aria-expanded", "false");
    }
  });

  // Handle search filtering
  searchInput.addEventListener("input", (e) => {
    renderModelList(e.target.value);
  });

  // Prevent dropdown closing when clicking inside search input
  searchInput.addEventListener("click", (e) => {
    e.stopPropagation();
  });

  // Load models from API
  try {
    // Show trigger loading state
    activeNameSpan.innerHTML = '<span class="loading-dot" style="display:inline-block; vertical-align:middle; margin-right:4px;"></span> Fetching...';
    trigger.disabled = true;

    const data = await ApiClient.getOllamaModels();
    
    trigger.disabled = false;
    allOllamaModels = data.models || [];
    activeOllamaModel = data.active_model || "";
    activeVisionModel = data.active_vision_model || "";

    if (data.error) {
      console.warn("Ollama model API returned error status:", data.error);
      if (statusIndicator) {
        statusIndicator.style.backgroundColor = "var(--bad)";
        statusIndicator.style.boxShadow = "0 0 8px var(--bad)";
      }
    } else {
      if (statusIndicator) {
        statusIndicator.style.backgroundColor = "var(--good)";
        statusIndicator.style.boxShadow = "0 0 8px var(--good)";
      }
    }

    updateActiveModelUI();
  } catch (err) {
    trigger.disabled = false;
    activeNameSpan.textContent = "Offline";
    if (statusIndicator) {
      statusIndicator.style.backgroundColor = "var(--bad)";
      statusIndicator.style.boxShadow = "0 0 8px var(--bad)";
    }
    console.error("Failed to load Ollama models:", err);
    renderEmptyState("Unable to reach Ollama host. Make sure it is running.");
  }

  function updateActiveModelUI() {
    if (activeOllamaModel) {
      activeNameSpan.textContent = cleanModelName(activeOllamaModel);
    } else {
      activeNameSpan.textContent = "Select Model";
    }
    renderModelList("");
  }

  function cleanModelName(rawName) {
    if (!rawName) return "Unknown";
    let name = rawName;
    if (name.includes(":")) {
      const parts = name.split(":");
      name = parts[0];
    }
    name = name.replace(/[-_]/g, " ");
    
    const lower = name.toLowerCase();
    if (lower.includes("llama3.2")) return "Llama 3.2";
    if (lower.includes("llama3.1")) return "Llama 3.1";
    if (lower.includes("llama3")) return "Llama 3";
    if (lower.includes("deepseek")) return "DeepSeek R1";
    if (lower.includes("qwen")) return "Qwen 2.5";
    if (lower.includes("gemma")) return "Gemma 3";
    if (lower.includes("moondream")) return "Moondream 2";
    
    return name.split(" ").map(word => {
      if (word.length === 0) return "";
      return word.charAt(0).toUpperCase() + word.slice(1);
    }).join(" ");
  }

  function formatSize(bytes) {
    if (!bytes || bytes === 0) return "0.0 GB";
    const gb = bytes / (1024 * 1024 * 1024);
    return `${gb.toFixed(1)} GB`;
  }

  function formatRelativeTime(isoString) {
    if (!isoString) return "";
    try {
      const date = new Date(isoString);
      if (isNaN(date.getTime())) return "";
      
      const now = new Date();
      const diffMs = now - date;
      const diffMins = Math.round(diffMs / 60000);
      const diffHours = Math.round(diffMs / 3600000);
      const diffDays = Math.round(diffMs / 86400000);
      
      if (diffMins < 1) return "Just now";
      if (diffMins < 60) return `${diffMins}m ago`;
      if (diffHours < 24) return `${diffHours}h ago`;
      if (diffDays < 30) return `${diffDays}d ago`;
      
      return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    } catch (e) {
      return "";
    }
  }

  function renderModelList(query) {
    listContainer.innerHTML = "";
    const filter = query.toLowerCase().trim();
    const filtered = allOllamaModels.filter(m => m.name.toLowerCase().includes(filter));

    if (filtered.length === 0) {
      if (allOllamaModels.length === 0) {
        renderEmptyState("No local Ollama models found. Pull models with `ollama pull`.");
      } else {
        renderEmptyState("No matching models found.");
      }
      return;
    }

    filtered.forEach(model => {
      const isTxtActive = model.name === activeOllamaModel || model.name.split(":")[0] === activeOllamaModel.split(":")[0];
      const isActive = isTxtActive;

      const item = document.createElement("div");
      item.className = `model-item ${isActive ? 'active-model' : ''}`;
      
      const isVision = model.name.includes("vision") || model.name.includes("moondream") || model.name.includes("minicpm") || model.name.includes("llava");
      const relativeTime = formatRelativeTime(model.modified_at);

      item.innerHTML = `
        <div class="model-item-info">
          <div class="model-item-header">
            <span class="model-item-name" title="${model.name}">${cleanModelName(model.name)}</span>
            <span class="model-item-status-badge ${isActive ? 'status-active' : 'status-available'}">
              ${isActive ? 'Active' : 'Available'}
            </span>
          </div>
          <div class="model-item-details">
            <span class="model-item-size">${formatSize(model.size_bytes)}</span>
            ${relativeTime ? `<span class="model-item-divider">•</span> <span class="model-item-modified">Modified ${relativeTime}</span>` : ''}
          </div>
        </div>
        ${isActive ? '<span class="model-item-check">✓</span>' : ''}
      `;

      item.addEventListener("click", async (e) => {
        e.stopPropagation();
        if (isActive) {
          trigger.classList.remove("open");
          dropdown.classList.remove("visible");
          trigger.setAttribute("aria-expanded", "false");
          return;
        }

        // Show overlay loader inside dropdown
        if (overlay) {
          overlay.querySelector(".loading-text").textContent = `Switching to ${cleanModelName(model.name)}...`;
          overlay.classList.add("show");
        }

        try {
          const res = await ApiClient.switchOllamaModel(model.name);
          
          if (overlay) overlay.classList.remove("show");
          trigger.classList.remove("open");
          dropdown.classList.remove("visible");
          trigger.setAttribute("aria-expanded", "false");

          if (res && res.status === "ok") {
            activeOllamaModel = model.name;
            showToast(`Switched active model to <strong>${cleanModelName(model.name)}</strong>`);
            loadSettings(); // refresh setting bindings
          } else {
            showToast("Failed to switch active model", true);
          }
        } catch (err) {
          console.error("Error switching model:", err);
          if (overlay) overlay.classList.remove("show");
          trigger.classList.remove("open");
          dropdown.classList.remove("visible");
          trigger.setAttribute("aria-expanded", "false");
          showToast("Network error switching active model", true);
        } finally {
          updateActiveModelUI();
        }
      });

      listContainer.appendChild(item);
    });
  }

  function renderEmptyState(message) {
    listContainer.innerHTML = `
      <div class="model-selector-empty">
        <div class="empty-icon">🧠</div>
        <div>${message}</div>
      </div>
    `;
  }

  function showToast(message, isError = false) {
    const toast = document.getElementById("model-switch-toast");
    const toastMsg = document.getElementById("model-switch-toast-message");
    const toastIcon = toast?.querySelector(".toast-icon");
    if (!toast || !toastMsg) return;

    toastMsg.innerHTML = message;
    if (isError) {
      toast.style.borderColor = "var(--bad-border)";
      if (toastIcon) toastIcon.textContent = "❌";
    } else {
      toast.style.borderColor = "var(--good-border)";
      if (toastIcon) toastIcon.textContent = "✅";
    }

    toast.classList.add("show");
    setTimeout(() => {
      toast.classList.remove("show");
    }, 4000);
  }
}
