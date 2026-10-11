function isVisionModel(name, provider) {
  if (!name) return false;
  const p = (provider || "").toLowerCase();
  if (p === "gemini") return true;
  const lower = name.toLowerCase();
  const visionKeywords = ["vision", "moondream", "llava", "bakllava", "minicpm-v", "scout", "multimodal", "-vl", "vl-", "_vl"];
  return visionKeywords.some(kw => lower.includes(kw));
}

export async function loadStepInfo(apiClient) {
  const client = apiClient || window.ApiClient || (typeof ApiClient !== "undefined" ? ApiClient : null);
  if (!client || typeof client.getSettings !== "function") {
    setTimeout(() => loadStepInfo(apiClient), 150);
    return;
  }
  const settings = await client.getSettings();

  const provider = settings.default_llm_provider || "ollama";
  const bannerBadge = document.getElementById("banner-provider-badge");
  if (bannerBadge) {
    bannerBadge.textContent = provider.toUpperCase();
    bannerBadge.className = `badge ${provider === "gemini" ? "likely_true" : (provider === "grok" ? "likely_true" : "inconclusive")}`;
  }

  const stepinfoCards = document.getElementById("stepinfo-cards");
  if (!stepinfoCards) return;
  stepinfoCards.innerHTML = "";

  const steps = [
    {
      num: 1,
      name: "AI Insights — First-Pass Content Review & Ingestion",
      desc: `This step performs initial content extraction, multimodal vision routing, OCR analysis, and prompt injection defense. It adapts dynamically based on input modality and active model capability:`,
      substeps: [
        `<strong>Text-only Inputs:</strong> The LLM reads raw claims, social media captions, or news snippets to synthesize the central proposition while flagging urgency language, emotional framing, and suspicious links.`,
        `<strong>Multimodal Vision Routing:</strong> Multimodal models with visual encoders (e.g. <em>Google Gemini</em>, <em>Grok 2 Vision</em>, <em>Llama 3.2 Vision</em>, or <em>Ollama Moondream</em>) inspect images and video frames directly alongside text and OCR metadata.`,
        `<strong>Text-Only Model Handling:</strong> For pure text language models (e.g. <em>GPT OSS 120B</em>, <em>Grok 4.1 Fast</em>, <em>Llama 3.2 1B</em>), the engine analyzes extracted OCR text context. If no text exists in the image, Step 1 returns an informative localized explanation advising the user to select a Vision model, while Step 2 proceeds with full offline forensic analysis.`,
        `<strong>Extension Snipping Protection:</strong> The browser extension verifies model modality beforehand; image snipping is blocked if a text-only model is active to prevent unhandled visual requests.`,
        `<strong>Tesseract-OCR Pipeline:</strong> Scans images via Tesseract OCR (<code>mcp_server.shared.ocr_utils</code>) to extract overlaid text. For videos, OpenCV grabs the initial frame for text recognition.`,
        `<strong>OpenCV Video Keyframe Probing:</strong> Extracts the initial representative keyframe (<code>_temp_step1_video_frame.jpg</code>) from video files for visual inspection and text extraction.`,
        `<strong>Prompt Injection Defense:</strong> Wraps prompts in strict security guardrails requiring the LLM to treat all inputs as untrusted raw data and ignore hidden instructions or override attempts.`,
        `<strong>Native Language Support:</strong> Synthesizes insights in the user's preferred language (<em>English</em>, <em>Taglish</em>, <em>Tagalog</em>, <em>Cebuano</em>, <em>Bisaya</em>, or <em>Ilocano</em>).`,
      ],
      output: "Returns a concise 2-4 sentence overview/summary, explanation, and extracted OCR text forwarded to Steps 2, 3, 4, and 5.",
      tech: ["LLM (Multimodal Vision or Text-Only)", "Tesseract OCR", "OpenCV (video keyframe capture)", "Prompt Injection Guardrails"],
      timeout: `${settings.pipeline_step_timeout_seconds || 120} seconds`,
      get_model: (s) => {
        if (s.default_llm_provider === "gemini") return s.gemini_model;
        if (s.default_llm_provider === "grok") return s.grok_model;
        return `${s.ollama_model} (text) / ${s.ollama_vision_model} (vision)`;
      }
    },
    {
      num: 2,
      name: "Content Analyser — Digital Media Forensics & Integrity",
      desc: `This step applies <em>offline local computer-vision forensics</em> to detect image manipulation, splices, and AI generation. <strong>Zero external network calls or cloud APIs are made — this is the fastest step in the pipeline.</strong> Runs exclusively on image and video inputs (text-only submissions bypass this step and are marked not applicable).`,
      substeps: [
        `<strong>Offline Local Execution:</strong> Computes all forensic signals locally with PIL, NumPy, and OpenCV for maximum speed, offline resilience, and data privacy.`,
        `<strong>Error Level Analysis (ELA):</strong> Re-compresses the image at 90% JPEG quality via Pillow and calculates the standard deviation of pixel difference variance scaled to a 0-100 suspicion score. Resaved or spliced regions display distinct compression error rates.`,
        `<strong>2D Fast Fourier Transform (FFT) Frequency Analysis:</strong> Converts image to 512x512 grayscale, computes 2D FFT (<code>np.fft.fft2</code> + <code>fftshift</code>), and calculates the ratio of high-frequency sensor noise to low-frequency energy using radial masking. Ratios below 0.15 indicate synthetic, smoothed AI generation patterns.`,
        `<strong>EXIF Metadata Forensics:</strong> Scans EXIF tags for camera hardware signatures (Make 271, Model 272, DateTime 306) and flags photo editing suites in tag 305 (Photoshop, GIMP, Snapseed, PicsArt, Canva).`,
        `<strong>Weighted Tri-Class Scoring:</strong><br>
         &bull; <code>Edited%</code> = <code>ELA &times; 0.8 + 25 (if editing software flagged)</code><br>
         &bull; <code>AI-Generated%</code> = <code>FFT Suspicion &times; 0.8 + 20 (if no camera hardware metadata)</code><br>
         &bull; <code>Real%</code> = <code>max(0, 100 &minus; Edited% &times; 0.5 &minus; AI% &times; 0.5)</code>, normalized to 100%.`,
        `<strong>Forensic Verdict Thresholds:</strong> <code>likely_ai_generated</code> (AI% &ge; 45), <code>likely_edited</code> (Edited% &ge; 45), <code>likely_authentic</code> (Real% &ge; 55), or <code>inconclusive</code>.`,
        `<strong>OpenCV Video Frame Sampling & Whisper Transcription:</strong> For videos, samples up to 24 frames (<code>max_video_frames</code>), classifies each frame independently, averages percentages across all frames, and transcribes audio via Faster-Whisper.`,
        `<strong>LLM Forensic Report:</strong> The active LLM synthesizes the mathematical signals into a user-friendly forensic explanation in the user's preferred language (falls back to static template if LLM is unavailable).`,
      ],
      output: "Real / Edited / AI-Generated percentage breakdown, forensic verdict, heuristic signals (ELA, FFT ratio, EXIF tags), video frame statistics & Whisper transcript, and forensic explanation.",
      tech: ["PIL / Pillow", "NumPy (2D FFT)", "OpenCV (video frame sampler)", "Faster-Whisper (speech transcription)", "LLM (forensic synthesis)"],
      timeout: `${settings.pipeline_step_timeout_seconds || 120} seconds`,
      get_model: (s) => {
        if (s.default_llm_provider === "gemini") return s.gemini_model;
        if (s.default_llm_provider === "grok") return s.grok_model;
        return s.ollama_vision_model || s.ollama_model;
      }
    },
    {
      num: 3,
      name: "Authenticity — Real-Time Fact-Checking & Source Verification",
      desc: `This step performs real-time fact-checking by combining claim extraction, live web search, RAG vector retrieval, domain trust scoring, and LLM evidence synthesis. It leverages context from Step 1 and forensic indicators from Step 2:`,
      substeps: [
        `<strong>Claim Extraction & Query Generation:</strong> Synthesizes the user claim, caption, OCR text, and Step 1/2 summaries into an optimized search query using stopword filtering (English & Filipino) and LLM query generation.`,
        `<strong>RAG Vector Store & Advisory Matching:</strong> Queries the local ChromaDB/SQLite vector store for prior verified investigations and official advisories (similarity threshold &ge; 0.45).`,
        `<strong>Multi-Engine Live Web Search:</strong> Dispatches queries to Google Custom Search API, automatically falling back to DuckDuckGo search if Google search is unavailable or unconfigured.`,
        `<strong>Domain Trust & Source Scoring Formula:</strong> Evaluates retrieved sources using a weighted formula: <code>60% Domain Trust + 40% Text Similarity</code>. Prioritizes Philippine government (<code>.gov.ph</code>), academic (<code>.edu.ph</code>), and certified fact-checkers (<code>factcheck.org</code>, accredited news).`,
        `<strong>Deep Page Content Scraping:</strong> When <code>STEP3_FETCH_FULL_PAGE=True</code> in <code>.env</code>, concurrently scrapes full article text via BeautifulSoup to provide rich context to the LLM.`,
        `<strong>Credibility Score & Verdict Thresholds:</strong> Computes credibility score (0-100) from top ranked sources: <strong>likely_true</strong> (score &ge; 70), <strong>inconclusive</strong> (score 45-69), or <strong>flagged</strong> (score &lt; 45).`,
        `<strong>Anti-Hallucination & Citation Rules:</strong> Forbids fabricating sources or links when search yields no results. When sources exist, generates clean clickable markdown links.`,
        `<strong>Continuous RAG Cache Ingestion:</strong> Automatically caches the resolved search query, score, verdict, and top sources back into the RAG vector store for instant future retrieval.`,
      ],
      output: "Credibility score (0-100), verdict (likely_true / inconclusive / flagged), comprehensive explanation with clickable source links, source rankings, and RAG cache matches.",
      tech: ["Google Custom Search API", "DuckDuckGo Search", "ChromaDB / SQLite (RAG vector store)", "BeautifulSoup", "LLM (evidence synthesis)"],
      timeout: `${settings.pipeline_step_timeout_seconds || 120} seconds`,
      get_model: (s) => {
        if (s.default_llm_provider === "gemini") return s.gemini_model;
        if (s.default_llm_provider === "grok") return s.grok_model;
        return s.ollama_model;
      }
    },
    {
      num: 4,
      name: "Actionable Items — Personalized Security Recommendations",
      desc: `This step translates findings from Steps 1, 2, and 3 into an actionable, tailored security checklist to protect the user against deception, scams, and digital threats:`,
      substeps: [
        `<strong>Multi-Step Threat Synthesis:</strong> Distills the Step 1 content insight, Step 2 media forensic breakdown (Real%, Edited%, AI%), and Step 3 fact-check score & verdict into a unified threat profile.`,
        `<strong>Verdict-Calibrated Protective Checklist:</strong><br>
         &bull; <strong>Flagged:</strong> Concrete defensive countermeasures (reporting malicious accounts/URLs, blocking scam numbers, enabling 2FA, contacting PNP Anti-Cybercrime Group or CICC hotline 1326).<br>
         &bull; <strong>Inconclusive:</strong> Verification actions (checking primary official government channels, avoiding amplifying unverified claims).<br>
         &bull; <strong>Likely True:</strong> Safe engagement hygiene and context validation.`,
        `<strong>Privacy & Anti-Hallucination Guardrails:</strong> Strictly forbids fabricating phone numbers, personal usernames, or fraudulent links.`,
        `<strong>Concurrent Execution:</strong> Executes concurrently with Step 5 for cloud LLMs (Gemini, Grok) via <code>asyncio.create_task</code>, or sequentially for local Ollama to conserve memory.`,
        `<strong>Native Language Delivery:</strong> Generated as a numbered list in the user's selected preferred language.`,
      ],
      output: "A numbered list of 3-5 concrete, prioritized actionable security recommendations.",
      tech: ["LLM (reasoning & synthesis)", "Cybersecurity Guardrails", "Async Concurrency"],
      timeout: `${settings.pipeline_step_timeout_seconds || 120} seconds`,
      get_model: (s) => {
        if (s.default_llm_provider === "gemini") return s.gemini_model;
        if (s.default_llm_provider === "grok") return s.grok_model;
        return s.ollama_model;
      }
    },
    {
      num: 5,
      name: "Learnings — Educational Resources & Digital Literacy",
      desc: `This step provides digital media literacy education, targeted discovery of official literacy resources, and voice narration:`,
      substeps: [
        `<strong>Manipulation Pattern Recognition:</strong> Explains the underlying manipulation tactics observed in the content (urgency triggers, impersonation, synthetic generation, emotional framing) in 2-3 accessible sentences.`,
        `<strong>Targeted Institutional Resource Discovery:</strong> Queries Google Custom Search specifically targeted at accredited institutional domains: <code>site:gov.ph OR site:edu.ph OR site:wikipedia.org OR site:factcheck.org</code>.`,
        `<strong>Noise & Anti-Spam Filtering:</strong> Programmatically removes generic academic noise (university course portals, unrelated faculties) and ad redirects so links directly educate the user on the specific scam or threat.`,
        `<strong>Verified Markdown Resource Links:</strong> Appends validated educational URLs as clean, clickable markdown citations.`,
        `<strong>Text-To-Speech (TTS) Narration:</strong> Converts the educational takeaway and summary into speech audio via the <code>/api/tts</code> endpoint (Google Cloud TTS / gTTS / pyttsx3 fallback) in the user's selected language and voice profile.`,
        `<strong>Concurrent Execution:</strong> Executes concurrently with Step 4 for cloud LLMs, or sequentially for local Ollama.`,
      ],
      output: "Educational literacy summary, concise bulleted tips, verified resource links, and TTS audio narration playback.",
      tech: ["Google Custom Search API", "Domain Trust Filter", "Google Cloud TTS / gTTS", "LLM (educational synthesis)"],
      timeout: `${settings.pipeline_step_timeout_seconds || 120} seconds`,
      get_model: (s) => {
        if (s.default_llm_provider === "gemini") return s.gemini_model;
        if (s.default_llm_provider === "grok") return s.grok_model;
        return s.ollama_model;
      }
    }
  ];

  for (const step of steps) {
    const activeModel = typeof step.get_model === "function" ? step.get_model(settings) : "";
    const isVis = isVisionModel(activeModel, provider);
    const substepsHtml = (step.substeps || []).map(s =>
      `<li style="margin-bottom:6px; line-height:1.5;">${s}</li>`
    ).join("");
    const techBadges = (step.tech || []).map(t =>
      `<span style="display:inline-block; font-size:11px; padding:2px 8px; border-radius:4px; background:rgba(99,102,241,0.12); color:var(--accent); border:1px solid rgba(99,102,241,0.25); margin:2px;">${t}</span>`
    ).join(" ");

    stepinfoCards.innerHTML += `
      <div class="card" style="display:flex; flex-direction:column; gap:10px; padding:20px; border-left: 4px solid var(--accent);">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
          <strong style="font-size:16px; color:var(--accent-light);">Step ${step.num}: ${step.name}</strong>
          <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
            <span style="font-size:11px; color:var(--muted); background:var(--bg); padding:3px 8px; border-radius:6px; border:1px solid var(--border);">
              ⏱ Timeout: <span style="font-family:monospace; color:var(--text);">${step.timeout}</span>
            </span>
            <span style="font-size:11px; color:var(--muted); background:var(--bg); padding:3px 8px; border-radius:6px; border:1px solid var(--border); display:inline-flex; align-items:center; gap:4px;">
              🤖 Model: <span style="font-family:monospace; color:var(--text);">${activeModel}</span>
              <span class="model-mode-badge ${isVis ? 'mode-vision' : 'mode-text'}">${isVis ? '👁️ Vision' : '📝 Text'}</span>
            </span>
          </div>
        </div>
        <div style="font-size:13px; line-height:1.5; color:var(--muted);">
          ${step.desc}
        </div>
        ${substepsHtml ? `
        <div style="margin-top:4px;">
          <div style="font-size:12px; font-weight:600; color:var(--text); margin-bottom:6px; text-transform:uppercase; letter-spacing:0.5px;">How it works:</div>
          <ol style="font-size:12.5px; color:var(--muted); margin:0; padding-left:20px; line-height:1.5;">
            ${substepsHtml}
          </ol>
        </div>` : ""}
        ${step.output ? `
        <div style="margin-top:4px; background:rgba(16,185,129,0.06); border:1px solid rgba(16,185,129,0.2); border-radius:8px; padding:10px 14px;">
          <div style="font-size:11px; font-weight:600; color:#10b981; margin-bottom:4px; text-transform:uppercase; letter-spacing:0.5px;">📤 Output</div>
          <div style="font-size:12.5px; color:var(--muted); line-height:1.4;">${step.output}</div>
        </div>` : ""}
        ${techBadges ? `
        <div style="margin-top:2px;">
          <span style="font-size:11px; color:var(--muted); margin-right:6px;">Technologies:</span>${techBadges}
        </div>` : ""}
      </div>`;
  }
}
