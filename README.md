# UsisAIn

A local-first, multimodal trust, fraud, scam, and misinformation detection system powered by a 5-step educational pipeline, reachable from two client channels: a **Chrome/Edge Browser Extension** (desktop) and a responsive **Web App & Analytics Dashboard**.

---

## 1. Project Structure

```
usisain/
├── backend-api/            # FastAPI gateway + pipeline orchestration + static web app server
│   └── src/usisain_backend/
│       ├── api/            # Stream, analyze, scans, tts, reference docs, settings, errors
│       ├── core/           # Configuration, logging
│       ├── data/           # SQLite database layer (app.db)
│       ├── extraction/     # Input normalization (text, image, video, post)
│       ├── orchestration/  # Sequential 5-step pipeline execution
│       └── services/       # MCP client integration
├── client/
│   ├── browser-extension/  # Desktop extension — right-click or snipping tool to verify
│   └── web-app/            # PWA web app & analytics dashboard (served at /app and /app/dashboard)
├── data/                   # Runtime state (gitignored except structure)
│   ├── models/             # Cached local models (whisper, etc.)
│   ├── reference_images/   # Verified documents for RAG comparison
│   ├── scripts/            # Ops scripts (init_db.py)
│   ├── uploads/            # Temporary file upload staging
│   └── vector_index/       # Local RAG cache (Step 3)
├── docs/                   # Documentation and architectural records
├── mcp_server/             # The 5 pipeline steps, implemented as Model Context Protocol tools
│   ├── services/llm/       # Providers (Ollama, Gemini, Grok) with key pools & fallback wrappers
│   ├── shared/             # Heuristics (ELA, DCT, EXIF, OCR optional fallback)
│   ├── tools/              # Step 1 (Insights) to Step 5 (Learnings)
│   └── server.py           # In-process MCP tool registration
├── tests/                  # Integration and unit tests
├── .env.example            # Environment template
├── .gitignore
├── README.md
└── requirements.txt
```

---

## 2. Architecture Recap

```
client/browser-extension ──┐
                           ├──► backend-api (FastAPI :8000) ──► mcp_server (5-step pipeline)
client/web-app ────────────┘         │                                    │
                                     ▼                                    ▼
                               SQLite (data/app.db)          Default: Ollama (Local)
                                                             Optional: Gemini / Grok (Cloud)
                                                             Fallback: Ollama (Automatic)
                                                             Search: Google Custom Search
                                                             Vector DB: Local RAG cache
```

- **`backend-api/`** — API gateway and orchestration layer (`usisain_backend/`).
  - `api/`: Domain-specific routers (`analyze`, `stream`, `scans`, `settings`, `reference_docs`, `errors`, `tts`).
  - `services/`: Encapsulated business logic services consumed via FastAPI `Depends`.
  - `orchestration/`: Pipeline decomposition (`step_runner`, `event_formatter`, `aggregator`, `pipeline`).
  - `data/repositories/`: Context-managed SQLite repositories for scans, reference documents, and error logs.
  - `core/`: Pydantic `BaseSettings` centralized configuration and system enums.
  - Streams step-by-step results in real time over SSE (`/api/analyze/stream`).
  - Returns aggregated JSON results for non-streaming callers (`/api/analyze`).
  - Generates speech from verified summaries (`/api/tts`).
  - Exposes runtime AI settings management (`/api/settings/ai`, `/api/settings/test-key`).
  - Directly serves the web application and dashboard at `/app` and `/app/dashboard`.
- **`mcp_server/`** — Modular 5-step pipeline registered as MCP tools and executed in-process inside the backend.
  - `steps/`: Typed dataclass inputs and outputs for Steps 1 through 5.
  - `prompts/`: Isolated LLM prompt definitions.
  - `services/llm/`: Standardized provider hierarchy (`BaseLLMProvider`, `OllamaProvider`, `GeminiProvider`, `GrokProvider`, `FallbackProvider`, `KeyPool`).
  - `constants.py`: Centralized scoring weights, thresholds, and forensic parameters.
- **`client/browser-extension/`** — Desktop browser extension. Right-click text, images, or video, or use the interactive **Usisain Snipping Tool** to crop any webpage region. Includes active LLM provider and model switcher in the popup.
- **`client/web-app/`** — Zero-build vanilla HTML5/CSS3/JavaScript ES modules client. Includes interactive verification modal, 30-day analytics, error logs, reference document RAG manager, and a dedicated **AI Settings** control center.

---

## 3. The 5-Step Analysis Pipeline

Every scan runs sequentially through a 5-step verification pipeline:

### Step 1: AI Insights (First-Pass Content Review)
* **Goal**: Provide an initial neutral overview and extract text/context.
* **How it works**:
  * **Text-only**: The LLM summarizes claims and flags urgent language, emotional framing, and suspicious links.
  * **Images & Video Frames**: Passed directly to multimodal vision models (**Gemini**, **Grok**, or **Ollama Vision**). If optical character recognition is desired, **Tesseract OCR** extracts text overlays; if Tesseract is not installed, the step gracefully falls back directly to visual LLM inference without errors.
  * **Usisain Snipping**: Extracts text and images within a user-drawn selection box on any webpage for unified analysis.
  * **Video**: Extracts keyframes using **OpenCV** to run visual analysis.
* **Outputs**: A concise summary of the content (passed to Steps 3, 4, and 5).
* **Tech**: LLM (Ollama / Gemini / Grok), OpenCV, Optional Tesseract OCR.

### Step 2: Content Analyser (Digital Image Forensics)
* **Goal**: Analyze images and videos locally for manipulation, edits, or AI generation signals. (Skipped for text-only inputs).
* **How it works**:
  * **Error Level Analysis (ELA)**: Re-saves the image at a known quality level (95%) and checks differences to find mismatched compression zones (e.g., spliced or pasted items).
  * **Frequency-Domain Analysis**: Runs a Discrete Cosine Transform (DCT) to check the ratio of high-to-low frequencies. Real camera sensors add high-frequency noise, while AI-generated images are unnaturally smooth or show periodic grid artifacts.
  * **EXIF Metadata**: Inspects headers for camera model information and editing software tags (Photoshop, GIMP, Canva, etc.).
  * **Percentage Breakdown**: Computes an estimated breakdown (Real% / Edited% / AI-Generated%) and assigns a verdict (`likely_authentic`, `likely_edited`, `likely_ai_generated`, or `inconclusive`).
  * **Forensic Explanation**: Multimodal models examine visual forensic signals and write a clear, user-friendly explanation of the breakdown percentages.
  * **Video Mode**: Samples frames via OpenCV, runs image heuristics on each frame, and averages results. Also transcribes audio (if present) using **Faster-Whisper**.
* **Outputs**: Percentage breakdown, forensic explanation, and video transcript.
* **Tech**: NumPy + SciPy (DCT), OpenCV, Pillow, Faster-Whisper, LLM.

### Step 3: Authenticity (Fact-Check & Source Verification)
* **Goal**: Cross-reference claims against fresh web search results and local reference documents.
* **How it works**:
  * **Search Query Generation**: Uses a fast heuristic query generator (`STEP3_FAST_QUERY_GEN=True`) to extract key entities and URLs from the claim text, with an LLM fallback.
  * **RAG Lookup**: Queries the local vector database for cached prior investigations and official advisories (reference documents) with a minimum score threshold of 0.45.
  * **Google Search**: Sends the query to the Google Custom Search API (with DuckDuckGo as fallback), retrieving up to 3 results.
  * **Source Scoring & Deduplication**: Scores results based on `Domain Trust (60%)` and `Text Similarity (40%)`. Deduplicates by URL and Title, selecting the top 2 sources.
  * **Page Scraping (Optional)**: If `STEP3_FETCH_FULL_PAGE=True`, fetches the webpage text of the top 2 sources in parallel using **ThreadPoolExecutor** and **BeautifulSoup** (up to 1,500 chars).
  * **LLM Synthesis**: The LLM evaluates search snippets, RAG advisories, and the claim. Assigns a verdict (`likely_true`, `inconclusive`, or `flagged`) and credibility score (0–100) with verified links.
  * **Cache Storage**: Caches the query, verdict, score, and top source URL into the RAG vector store for instant future lookups.
* **Outputs**: Credibility score (0–100), verdict, and scored sources.
* **Tech**: Google Custom Search API, RAG Vector Store, BeautifulSoup, LLM.

### Step 4: Actionable Items (Personalized Security Recommendations)
* **Goal**: Provide 3–5 concrete next-step recommendations tailored to the verdict.
* **How it works**:
  * **Likely True**: Promotes safe engagement and official link checking.
  * **Flagged / Scam**: Recommends defensive measures (block account, unfollow, report, warn others).
  * **Inconclusive**: Advises caution and further manual verification.
  * **Privacy Guard**: Strict rules prevent the LLM from outputting usernames, handles, or private personal data.
* **Outputs**: A numbered list of 3–5 concrete action items.
* **Tech**: LLM.

### Step 5: Learnings (Educational Resources & Digital Literacy)
* **Goal**: Educate the user on threat patterns and provide credible digital literacy links.
* **How it works**:
  * Generates an educational search query and fetches verified educational resources from official domains (`site:gov.ph`, `site:edu.ph`, `wikipedia.org`, `factcheck.org`).
  * The LLM writes a 2–3 sentence educational overview explaining the threat pattern (e.g. emotional framing, clickbait, phishing).
  * To prevent hallucination, the LLM is prohibited from generating URLs — verified educational links are programmatically appended by Python.
* **Outputs**: 2–3 sentence educational synthesis and clickable official learning links.
* **Tech**: Google Custom Search API, LLM.

---

## 4. AI Providers & Runtime Architecture

UsisAIn supports three LLM backends:

| Provider | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| **Ollama** | **Local / Offline** | **Yes (Default)** | Default engine. Runs 100% locally on your machine with zero API key required. |
| **Google Gemini** | **Cloud API** | *Optional* | Cloud alternative supporting Gemini 3.5 Flash, 2.5 Flash/Pro, 2.0 Flash, etc. |
| **xAI Grok** | **Cloud API** | *Optional* | Cloud alternative supporting gpt-oss-120b (default), Grok 4.1 Fast, Grok 4.7, Grok 4.20 Reasoning, Grok Beta, etc. |

### Smooth Runtime Transition & Automatic Fallback
- **Ollama as Default & Auto-Detection on Failure**: Ollama is the default offline engine. If Ollama is not installed, not running, or fails on run, the system automatically inspects `.env` for configured cloud API keys (`GROK_API_KEY` or `GEMINI_API_KEY`) and auto-selects that provider (e.g. Grok `gpt-oss-120b`) as the active default AI and model with zero manual intervention.
- **Zero-Restart Key & Model Updates**: Change active models or update API keys in real time via the Web App Dashboard (**⚙️ AI Settings** tab). Keys are reloaded into memory instantly and saved to `.env`.
- **Multi-Key Pool & Rotation**: Both Gemini and Grok support comma-separated keys (`key1,key2`) with automatic round-robin load distribution.

---

## 5. Prerequisites (Windows)

1. **Python 3.12+ (64-bit)**
   - Download from https://www.python.org/downloads/
2. **Ollama (Default Local AI — Optional if using Cloud AI)**
   - Recommended for 100% offline, privacy-first local analysis. If Ollama is uninstalled or unreachable, the system automatically uses whichever cloud AI key (`GROK_API_KEY` or `GEMINI_API_KEY`) is set in your `.env`.
   - Download from https://ollama.com/download/windows
   - Pull the recommended models:
     ```powershell
     ollama pull llama3.2:1b
     ollama pull moondream
     ollama pull nomic-embed-text
     ```
3. **Tesseract OCR (Optional)**
   - Purely optional. When uninstalled or disabled, image and video visual verification runs directly through multimodal vision models (Gemini, Grok, or Ollama Vision) without warnings or errors.
   - If desired for OCR text extraction: installer available at https://github.com/UB-Mannheim/tesseract/wiki.

---

## 6. API Keys (Search & Optional Cloud AI)

| Key | Required? | Where to get it |
| :--- | :--- | :--- |
| `GOOGLE_API_KEY` | **Required for Fact-Check** | https://console.cloud.google.com/apis/credentials (Enable "Custom Search API") |
| `GOOGLE_CSE_ID` | **Required for Fact-Check** | https://programmablesearchengine.google.com/ (Search engine ID) |
| `GEMINI_API_KEY` | *Optional* | https://aistudio.google.com/apikey (or configure via Dashboard AI Settings) |
| `GROK_API_KEY` | *Optional* | https://console.x.ai/ (or configure via Dashboard AI Settings) |

---

## 7. Setup & Installation

```powershell
# 1. Clone repository and enter directory
cd usisain-hackathon

# 2. Create and activate virtual environment
py -m venv venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy environment configuration
copy .env.example .env

# 5. Initialize the database
python data\scripts\init_db.py
```

---

## 8. Running the Application

Start the backend API server and static web app:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\run.bat
```

Alternatively, run directly with Uvicorn:
```powershell
.\venv\Scripts\python -m uvicorn usisain_backend.main:app --host 0.0.0.0 --port 8000 --reload --app-dir backend-api\src
```

- **Backend API & Docs**: http://localhost:8000/docs
- **Web App**: http://localhost:8000/app
- **Admin & Analytics Dashboard**: http://localhost:8000/app/dashboard

---

## 9. Browser Extension Setup (Desktop)

1. Open your browser and navigate to `chrome://extensions` (Chrome) or `edge://extensions` (Edge).
2. Enable **Developer mode** (toggle in top right).
3. Click **Load unpacked** and select the directory:
   `c:\Projects\Usisain\usisain-hackathon\client\browser-extension\`
4. Keep the backend running on port 8000.
5. **Usage**:
   - Right-click selected text, an image, or a video on any website to verify.
   - Click the extension icon and use the **Usisain Snipping Tool** to draw a box around any part of a page.
   - Switch active LLM providers (Ollama, Gemini, Grok) or specific models right from the extension popup.

---

## 10. Web App & Dashboard Features

With the backend running, open **`http://localhost:8000/app/dashboard`**:

1. **Overview Tab**:
   - Total Scans, Credible/Safe, Inconclusive, and Flagged counts.
   - 30-day interactive scan trends chart by client channel.
   - Visual verdict distribution doughnut chart.
   - Audit scan history table with filtering, search, and full JSON inspection.
2. **Reference Documents Tab**:
   - Upload official advisories, government notices, and ground-truth documents.
   - Automatically vectorized locally via `nomic-embed-text` for semantic matching in Step 3.
3. **⚙️ AI Settings Tab**:
   - **Default Provider Selector**: Choose between Ollama, Gemini, and Grok with instant live switching.
   - **Ollama Card**: View local host connection, active text model, active vision model, and refresh available models.
   - **Google Gemini Card**: Add/update API keys, toggle key visibility, switch active Gemini models, and run a **⚡ Test Key** connection check.
   - **xAI Grok Card**: Add/update API keys, toggle key visibility, switch active Grok models, and run a **⚡ Test Key** connection check.
   - **Tesseract OCR Engine Card**: Live status indicator displaying whether Tesseract is active or operating in automatic multimodal vision fallback mode.
4. **Error Log Tab**:
   - Real-time logging of pipeline step timeouts or warnings with one-click cleanup.
5. **Pipeline Info Tab**:
   - Visual diagram and technical breakdown of all 5 steps with live model badges.

---

## 11. Localization & Multilingual Support

The system supports multilingual analysis across all LLM-driven steps (Steps 1, 4, and 5):
- **English** (Supported across Ollama, Gemini, and Grok)
- **Taglish** (Gemini & Grok)
- **Tagalog / Filipino** (Gemini & Grok)
- **Cebuano** (Gemini & Grok)
- **Bisaya** (Gemini & Grok)
- **Ilocano** (Gemini & Grok)

---

## 12. Troubleshooting

- **Connection Error in Extension / Web App**: Ensure backend is running on `http://localhost:8000`.
- **Ollama Offline**: Ensure `ollama serve` is active in the background. Verify model availability with `ollama list`.
- **Search API Errors (Step 3)**: Verify `GOOGLE_API_KEY` and `GOOGLE_CSE_ID` in `.env`.
- **Cloud Key Test Fails**: Open the **⚙️ AI Settings** tab in the Dashboard, re-enter your API key, and click **⚡ Test Key** to see the diagnostic response.
- **Tesseract Not Found Warning**: Tesseract is strictly optional. The pipeline will automatically route image verification to multimodal vision models.
