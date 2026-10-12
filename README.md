# UsisAIn

**A local-first, multimodal trust, fraud, scam, and misinformation detection system, powered by a 5-step educational pipeline.**

UsisAIn checks text, images, and video for scams, manipulation, and misinformation, then explains *why* a piece of content is risky and what to do about it. It runs fully offline with a local model (Ollama) by default, and can optionally use cloud models (Gemini, Grok/Groq).

It is reachable from two client channels:

- **Cross-browser extension**: Chrome, Edge, Brave, Opera, Firefox, Safari
- **Web app and analytics dashboard**: responsive PWA served by the backend

---

## Table of Contents

- [Key Features](#key-features)
- [Quick Start](#quick-start)
  - [Option A: Install with Windows Installer (.msi)](#option-a-install-with-windows-installer-msi--recommended)
  - [Option B: Run on macOS (Universal Package)](#option-b-run-on-macos-universal-package)
  - [Option C: Run from source (developers)](#option-c-run-from-source-developers)
- [How It Works: The 5-Step Pipeline](#how-it-works-the-5-step-pipeline)
- [AI Providers](#ai-providers)
- [Configuration](#configuration)
- [Dynamic Port Management & Auto-Restart](#dynamic-port-management--auto-restart)
- [Browser Extension](#browser-extension)
- [Web App and Dashboard](#web-app-and-dashboard)
- [Language Support](#language-support)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Desktop Launcher and Packaging](#desktop-launcher-and-packaging)
- [Troubleshooting](#troubleshooting)

---

## Key Features

| Feature | Description |
| :--- | :--- |
| **Local-first AI** | Runs 100% offline with Ollama. No API key required. |
| **Multimodal analysis** | Text, images, video frames, and user-selected screen regions. |
| **Digital image forensics** | ELA, DCT frequency analysis, and EXIF inspection estimate Real / Edited / AI-generated percentages. |
| **Fact-checking with sources** | Cross-references claims against web search and your own reference documents (RAG). |
| **Actionable guidance** | 3-5 concrete next steps tailored to the verdict. |
| **Digital literacy** | Educational explanations with verified links from official domains. |
| **Multilingual** | English, Taglish, Tagalog, Cebuano, Bisaya, Ilocano. |
| **Hot-swappable AI** | Change models and API keys live from the dashboard, no restart. |
| **Automatic fallback** | If Ollama is offline, falls back to any configured cloud key. |

---

## Quick Start

### Option A: Install with Windows Installer (.msi) — Recommended

> Recommended for general users, reviewers, and evaluators. No Python or command line required.

1. **Get the installer:**
   - **Download pre-built:** Download **`UsisAIn-Setup.msi`** (or portable **`UsisAIn-windows-x64.zip`**) from [GitHub Releases](https://github.com/MansanasCatch/usisain-hackathon/releases) *(binary installer files are published under Releases rather than tracked in git)*.
   - **Or build locally:** If you cloned the repository, run `.\desktop\build_windows.ps1` to generate **`desktop/dist/UsisAIn-Setup.msi`** on your machine.
2. **Install:**
   - Double-click **`UsisAIn-Setup.msi`**.
   - Review and accept the educational open-source Terms and Media Literacy License Agreement (no generic placeholders).
   - Follow the setup wizard (**Next** ➔ **Install**).
   - This automatically installs UsisAIn into `Program Files\UsisAIn` and places shortcuts on your **Desktop** and **Start Menu**.
3. **Launch:**
   - Double-click the **UsisAIn** shortcut on your Desktop or Start Menu.
   - The launcher will:
     - Detect your default browser,
     - Automatically preload the UsisAIn extension,
     - Open the dashboard at `http://localhost:8000/app/dashboard` (or custom configured port).
   - Closing the launcher window (or clicking **Quit**) stops all background processes and frees the port.
   - Easily switch ports anytime from the launcher status window using the **Change Port** button (auto-restarts smoothly).
4. **Configure AI (one time)** in the dashboard under **AI Settings**:
   - **Offline / local (Ollama):** If Ollama is running and default models are missing, UsisAIn guides you or pulls them automatically. Ensure a text reasoning model like `llama3.2:1b` is selected for text synthesis, with `moondream` or `llama3.2-vision` for vision analysis.
   - **Cloud:** Paste a Gemini or Grok/Groq key, click **Update Key** (applies instantly), then **Test Key**. See [Configuration](#configuration) for where to get keys.

> To uninstall anytime, open Windows **Settings** ➔ **Installed apps** (or Control Panel ➔ Programs and Features) and click **Uninstall** on **UsisAIn**.
> Your data, logs, and API keys are stored in `%LOCALAPPDATA%\UsisAIn\app`.

### Option B: Run on macOS (Universal Package)

> Recommended for macOS users. No git clone or manual environment setup needed.

1. **Download the macOS release:**
   - Download **`UsisAIn-macos-universal.zip`** from [GitHub Releases](https://github.com/MansanasCatch/usisain-hackathon/releases).
2. **Extract and launch:**
   - Unzip `UsisAIn-macos-universal.zip`.
   - Open Terminal in the extracted folder and run:
     ```bash
     chmod +x run_macos.sh
     ./run_macos.sh
     ```
   - This automatically creates the local virtual environment, installs dependencies, verifies database tables, loads the browser extension, and opens your default browser at `http://localhost:8000/app/dashboard`.
3. **Build Native macOS .app or .dmg (Optional):**
   - If you have Xcode or command-line tools installed, run `./desktop/build_macos.sh` to generate native `UsisAIn.app` and `UsisAIn-macOS.dmg` bundles.

### Option C: Run from source (developers)

> Recommended if you're modifying the AI pipeline, backend, or extension.

**Prerequisites**

| Requirement | Notes |
| :--- | :--- |
| Python 3.12+ (64-bit) | https://www.python.org/downloads/ |
| Git | |
| Ollama *(optional)* | Default local AI. Skip if you only use cloud keys. https://ollama.com/download/windows |
| Tesseract OCR *(optional)* | Only for OCR text extraction. [Installer](https://github.com/UB-Mannheim/tesseract/wiki) |

**1. Clone and install**

```powershell
git clone https://github.com/MansanasCatch/usisain-hackathon.git
cd usisain-hackathon

py -m venv venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\activate

pip install -r requirements.txt
pip install -r desktop/requirements-build.txt   # only needed for desktop packaging
copy .env.example .env
python data\scripts\init_db.py
```

**2. (Optional) Pull the local models**

```powershell
ollama pull llama3.2:1b
ollama pull moondream
ollama pull nomic-embed-text
```

**3. Run**

```powershell
# Recommended: one command, auto-preloads the extension and opens the dashboard
python run.py
```

<details>
<summary>Other ways to run</summary>

```powershell
# Uvicorn directly (with hot reload)
.\venv\Scripts\python -m uvicorn usisain_backend.main:app --host 0.0.0.0 --port 8000 --reload --app-dir backend-api\src

# Batch script
.\run.bat

# Desktop launcher GUI
$env:PYTHONPATH = "desktop;$env:PYTHONPATH"
python -m usisain_launcher
```

</details>

**Endpoints**

| Service | URL |
| :--- | :--- |
| Analytics dashboard | http://localhost:8000/app/dashboard |
| Web app | http://localhost:8000/app |
| Interactive API docs | http://localhost:8000/docs |

---

## How It Works: The 5-Step Pipeline

Every scan runs sequentially through five steps. Each step's results are streamed to the client in real time over SSE.

```
Input ─► 1. Insights ─► 2. Content Analyser ─► 3. Authenticity ─► 4. Actions ─► 5. Learnings
         (summary)      (image/video forensics)  (fact-check)       (next steps)   (education)
```

### Step 1: AI Insights (first-pass review)

Gives a neutral overview of the content and extracts text and context.

- **Text:** the LLM summarizes claims and flags urgent language, emotional framing, and suspicious links.
- **Images and video frames:** sent to a multimodal model (Gemini, Grok, or Ollama Vision). If Tesseract OCR is installed and active, it extracts high-precision text overlays while leaving you free to choose any multimodal model for visual analysis. Without OCR, the pipeline directly performs visual LLM inference smoothly.
- **Snipping tool:** extracts text and images from a user-drawn region on any webpage.
- **Video:** extracts keyframes with OpenCV.
- **Output:** a concise summary passed to Steps 3, 4, and 5.
- **Tech:** LLM, OpenCV, optional Tesseract.

### Step 2: Content Analyser (digital image forensics)

Analyzes images and video locally for manipulation or AI generation. *Skipped for text-only input.*

| Technique | What it does |
| :--- | :--- |
| **Error Level Analysis (ELA)** | Re-saves the image at 95% quality and compares differences to find mismatched compression zones (spliced or pasted items). |
| **Frequency-domain (DCT)** | Checks the high-to-low frequency ratio. Camera sensors add high-frequency noise; AI images tend to be unnaturally smooth or show periodic grid artifacts. |
| **EXIF metadata** | Looks for camera model info and editing-software tags (Photoshop, GIMP, Canva, etc.). |
| **Percentage breakdown** | Estimates Real % / Edited % / AI-Generated % and assigns a verdict: `likely_authentic`, `likely_edited`, `likely_ai_generated`, or `inconclusive`. |
| **Forensic explanation** | A multimodal model explains the breakdown in plain language. |
| **Video mode** | Samples frames with OpenCV, averages the image heuristics, and transcribes audio with Faster-Whisper. |

- **Output:** percentage breakdown, explanation, and video transcript.
- **Tech:** NumPy, SciPy, OpenCV, Pillow, Faster-Whisper, LLM.

### Step 3: Authenticity (fact-check and source verification)

Cross-references claims against fresh web results and your local reference documents.

1. **Query generation:** a fast heuristic extracts key entities and URLs (`STEP3_FAST_QUERY_GEN=True`), with an LLM fallback.
2. **Relevance and entity filter:** strict entity and relevance filtering prevents appending unrelated named entities or off-topic links (e.g. noise from query anomalies or unmatched RAG vectors). Only sources directly matching the claim are retained.
3. **RAG lookup:** searches the local vector store for cached investigations and official advisories (minimum score 0.45).
4. **Web search:** Google Custom Search (DuckDuckGo as fallback), up to 3 results.
5. **Scoring and dedup:** sources are scored by Domain Trust (60%) and Text Similarity (40%), deduplicated by URL and title, and the top 2 are kept.
6. **Page scraping (optional):** with `STEP3_FETCH_FULL_PAGE=True`, fetches up to 1,500 characters from the top 2 sources in parallel (ThreadPoolExecutor + BeautifulSoup).
7. **LLM synthesis:** weighs snippets, advisories, and the claim, then returns a verdict (`likely_true`, `inconclusive`, `flagged`) and a credibility score (0-100) with verified links.
8. **Caching:** stores the query, verdict, score, and top source URL in the RAG store for instant future lookups.

- **Output:** credibility score, verdict, and scored sources.
- **Tech:** Google Custom Search API, RAG vector store, BeautifulSoup, LLM.

### Step 4: Actionable Items (security recommendations)

Produces 3-5 concrete next steps tailored to the verdict.

| Verdict | Guidance |
| :--- | :--- |
| Likely true | Engage safely and check official links. |
| Flagged / scam | Defensive measures: block, unfollow, report, warn others. |
| Inconclusive | Stay cautious and verify manually. |

**Privacy guard:** strict rules prevent the LLM from outputting usernames, handles, or private personal data.

### Step 5: Learnings (digital literacy)

Teaches users to recognize the threat pattern.

- Builds an educational query and fetches resources from trusted domains (`site:gov.ph`, `site:edu.ph`, `wikipedia.org`, `factcheck.org`).
- The LLM writes a 2-3 sentence overview of the pattern (emotional framing, clickbait, phishing, etc.).
- **Model refusal protection:** if a local vision model responds with a deprecation or capability disclaimer, UsisAIn activates automatic educational fallbacks, ensuring users always receive clear, authoritative media literacy guidance.
- **Anti-hallucination:** the LLM is prohibited from generating URLs. Verified links are appended programmatically by Python.
- **Tech:** Google Custom Search API, LLM.

---

## AI Providers

| Provider | Type | Default | Notes |
| :--- | :--- | :---: | :--- |
| **Ollama** | Local / offline | Yes | Runs entirely on your machine. No API key needed. |
| **Google Gemini** | Cloud | No | Supports Gemini 3.5 Flash, 2.5 Flash/Pro, 2.0 Flash, and more. |
| **xAI Grok / Groq** | Cloud | No | gpt-oss-120b (default), Grok 4.1 Fast, Grok 4.7, Grok 4.20 Reasoning, Grok Beta, and more. |

**Runtime behavior**

- **Ollama auto-detection:** when Ollama is online, the backend checks for `llama3.2:1b` and pulls it in the background if missing, with live progress on the dashboard.
- **Automatic fallback:** if Ollama is offline or not installed, UsisAIn uses whichever cloud key (`GROK_API_KEY` or `GEMINI_API_KEY`) is configured. No manual switching needed.
- **Zero-restart updates:** change models or keys from **AI Settings**. Keys reload into memory instantly and are saved to `.env`.
- **Key pools:** Gemini and Grok accept comma-separated keys (`key1,key2`) with round-robin load distribution.

---

## Configuration

Set these in `.env` (copied from `.env.example`) or through the dashboard.

| Key | Required? | Where to get it |
| :--- | :--- | :--- |
| `GOOGLE_API_KEY` | **Required for fact-check** | [Google Cloud Credentials](https://console.cloud.google.com/apis/credentials) (enable *Custom Search API*) |
| `GOOGLE_CSE_ID` | **Required for fact-check** | [Programmable Search Engine](https://programmablesearchengine.google.com/) (your search engine ID) |
| `GEMINI_API_KEY` | Optional (recommended) | [Google AI Studio](https://aistudio.google.com/apikey) (free tier) |
| `GROK_API_KEY` | Optional | [xAI Console](https://console.x.ai/) or [Groq Console](https://console.groq.com/keys) |

### Getting a free Gemini key

1. Open [Google AI Studio](https://aistudio.google.com/apikey) and sign in.
2. Click **Create API key** and pick (or create) a Google Cloud project.
3. Copy the key (starts with `AIzaSy...`).
4. In the dashboard, open **AI Settings**, paste it into the **Google Gemini** card, click **Update Key**, then **Test Key**.

### Getting a Grok or Groq key

UsisAIn supports both and routes automatically by key prefix.

<details>
<summary><strong>xAI Grok</strong> (key starts with <code>xai-</code>)</summary>

1. Sign in at the [xAI Console](https://console.x.ai/).
2. Go to **API Keys** and click **Create API Key**.
3. Paste it into **AI Settings** under the Grok card and click **Update Key**.

</details>

<details>
<summary><strong>Groq Cloud</strong> (key starts with <code>gsk_</code>)</summary>

1. Sign in at the [Groq Console](https://console.groq.com/keys) (free with Google or GitHub).
2. Click **Create API Key**, name it, and copy it.
3. Paste it into **AI Settings** under the Grok card and click **Update Key**.
4. UsisAIn detects the `gsk_` prefix and routes inference to Groq's `llama-3.3-70b-versatile`.

</details>

---

## Dynamic Port Management & Auto-Restart

UsisAIn provides native port configuration and instant hot restart:

- **From GUI Desktop Launcher:** Click **Change Port** on the Status Window, enter your target port (e.g. `8080`), and click **Restart Server**. UsisAIn will automatically:
  1. Save the new port to `.env` and runtime preferences.
  2. Gracefully terminate the current server process without leaving dangling child tasks.
  3. Spin up the backend on the new port and update the dashboard link.
- **From CLI / Terminal:** Specify `--port <number>` or set the `PORT` environment variable:
  ```powershell
  # Windows
  python run.py --port 8080
  
  # macOS / Linux
  ./run_macos.sh --port 8080
  ```

---

## Browser Extension

One shared codebase supports Chromium (MV3), Firefox (Gecko MV3), and Safari, using a compatibility shim (`compat.js`) and cross-browser manifest generators.

### Extension features

- **Right-click menu:** verify text, images, and video directly from any page.
- **Snipping tool:** draw a box over any screen area for combined text and image analysis.
- **Provider and model switcher:** switch between Ollama, Gemini, and Grok from the popup.
- **Text-to-speech:** listen to audio summaries of verdicts.

### Installation

**Easiest: via the desktop launcher.** Run `UsisAIn.exe` (or `python -m usisain_launcher`). It detects your browser, shows a native prompt, opens the extensions page, and copies the extension folder path to your clipboard.

**Manual installation**

<details>
<summary><strong>Chrome, Edge, Brave, Opera (Chromium MV3)</strong></summary>

1. Open your browser's extensions page:

   | Browser | URL |
   | :--- | :--- |
   | Chrome | `chrome://extensions` |
   | Edge | `edge://extensions` |
   | Brave | `brave://extensions` |
   | Opera | `opera://extensions` |

2. Enable **Developer mode**.
3. Click **Load unpacked** and select the `client/browser-extension/` folder from your clone (or `desktop\dist\UsisAIn\_internal\payload\extension\chromium` in a built package).
4. Pinned extension ID: `dndlahijonngmpkomafkmiainhmkplnp`.

</details>

<details>
<summary><strong>Mozilla Firefox (Gecko MV3)</strong></summary>

1. Go to `about:debugging#/runtime/this-firefox`.
2. Click **Load Temporary Add-on...**.
3. Select `desktop\build\extension\firefox\manifest.json` (generate it with `python desktop\tools\build_extension.py`).
4. Extension ID: `usisain@usisain.app`.

</details>

<details>
<summary><strong>Apple Safari (Safari Web Extension)</strong></summary>

1. On macOS with Xcode installed, run `./desktop/build_macos.sh` to wrap the extension as `UsisAIn Extension.app`.
2. Open Safari, then **Settings**, then **Extensions**, enable **UsisAIn**, and choose **Always Allow on Every Website**.

</details>

---

## Web App and Dashboard

With the backend running, open **http://localhost:8000/app/dashboard**.

| Tab | What you get |
| :--- | :--- |
| **Overview** | Total scans plus Credible, Inconclusive, and Flagged counts. A 30-day scan trend chart by client channel, a verdict distribution chart, and an audit history table with filtering, search, and full JSON inspection. |
| **Reference Documents** | Upload official advisories and ground-truth documents. They are vectorized locally with `nomic-embed-text` for semantic matching in Step 3. |
| **AI Settings** | Default provider selector with instant switching. Ollama card (live status, install guide, auto-pull with progress). Gemini and Grok cards (update key, toggle visibility, switch model, **Test Key**). Tesseract card (active vs. vision-fallback mode). |
| **Error Log** | Real-time pipeline timeouts and warnings, with one-click cleanup. |
| **Pipeline Info** | Interactive diagram of all 5 steps with live model badges and parameters. |

---

## Language Support

Steps 1, 4, and 5 (the LLM-driven steps) support multilingual analysis.

| Language | Supported on |
| :--- | :--- |
| English | Ollama, Gemini, Grok |
| Taglish | Gemini, Grok |
| Tagalog / Filipino | Gemini, Grok |
| Cebuano | Gemini, Grok |
| Bisaya | Gemini, Grok |
| Ilocano | Gemini, Grok |

---

## Architecture

```
client/browser-extension ──┐
                           ├──► backend-api (FastAPI :8000) ──► mcp_server (5-step pipeline)
client/web-app ────────────┘         │                                    │
                                     ▼                                    ▼
                               SQLite (data/app.db)          Default:  Ollama (local)
                                                             Optional: Gemini / Grok (cloud)
                                                             Fallback: Ollama (automatic)
                                                             Search:   Google Custom Search
                                                             Vector:   local RAG cache
```

**`backend-api/`**: API gateway and orchestration (`usisain_backend/`)

- `api/`: routers for `analyze`, `stream`, `scans`, `settings`, `reference_docs`, `errors`, `tts`
- `services/`: business logic injected via FastAPI `Depends`
- `orchestration/`: pipeline decomposition (`step_runner`, `event_formatter`, `aggregator`, `pipeline`)
- `data/repositories/`: context-managed SQLite repositories for scans, reference docs, and error logs
- `core/`: Pydantic `BaseSettings` configuration and system enums

**Key endpoints**

| Endpoint | Purpose |
| :--- | :--- |
| `/api/analyze/stream` | Step-by-step results over SSE |
| `/api/analyze` | Aggregated JSON for non-streaming callers |
| `/api/tts` | Speech from verified summaries |
| `/api/settings/ai`, `/api/settings/test-key` | Runtime AI settings management |
| `/app`, `/app/dashboard` | Static web app and dashboard |

**`mcp_server/`**: the 5 pipeline steps as Model Context Protocol tools, executed in-process

- `steps/`: typed dataclass inputs and outputs for Steps 1-5
- `prompts/`: isolated LLM prompt definitions
- `services/llm/`: provider hierarchy (`BaseLLMProvider`, `OllamaProvider`, `GeminiProvider`, `GrokProvider`, `FallbackProvider`, `KeyPool`)
- `constants.py`: scoring weights, thresholds, and forensic parameters

**`client/`**

- `browser-extension/`: Chromium MV3 and Firefox Gecko extension
- `web-app/`: zero-build vanilla HTML5/CSS3/JS (ES modules) PWA and dashboard

---

## Project Structure

```
usisain/
├── backend-api/              # FastAPI gateway, orchestration, static web app server
│   └── src/usisain_backend/
│       ├── api/              # Stream, analyze, scans, tts, reference docs, settings, errors
│       ├── core/             # Configuration, logging
│       ├── data/             # SQLite database layer (app.db)
│       ├── extraction/       # Input normalization (text, image, video, post)
│       ├── orchestration/    # Sequential 5-step pipeline execution
│       └── services/         # MCP client integration
├── client/
│   ├── browser-extension/    # Cross-browser extension (Chromium MV3 and Firefox Gecko)
│   └── web-app/              # PWA web app and analytics dashboard
├── data/                     # Runtime state (gitignored except structure)
│   ├── models/               # Cached local models (whisper, etc.)
│   ├── reference_images/     # Verified documents for RAG comparison
│   ├── scripts/              # Ops scripts (init_db.py)
│   ├── uploads/              # Temporary upload staging
│   └── vector_index/         # Local RAG cache (Step 3)
├── desktop/                  # Standalone launcher and cross-platform packaging
│   ├── assets/               # Master icons (.ico, .icns, PNGs)
│   ├── tools/                # make_icons.py, build_extension.py
│   ├── usisain_launcher/     # Native launcher (detection, dialogs, runtime sync)
│   ├── build_windows.ps1     # Windows bundle builder (.exe and zip)
│   ├── build_macos.sh        # macOS builder (.app and .dmg)
│   ├── usisain.spec          # PyInstaller one-folder spec
│   └── requirements-build.txt
├── docs/                     # Documentation and architecture records
├── mcp_server/               # The 5 pipeline steps as MCP tools
│   ├── services/llm/         # Ollama, Gemini, Grok providers, key pools, fallback
│   ├── shared/               # Heuristics (ELA, DCT, EXIF, optional OCR)
│   ├── tools/                # Step 1 (Insights) to Step 5 (Learnings)
│   └── server.py             # In-process MCP tool registration
├── tests/                    # Integration, unit, and launcher tests
├── .env.example
├── requirements.txt
└── README.md
```

---

## Desktop Launcher and Packaging

The desktop launcher packages UsisAIn as a standalone executable with custom icons. On launch it detects your browser and offers to install the extension.

### Build

```powershell
# Windows: builds standalone .exe, .msi installer, and release zip
.\desktop\build_windows.ps1
```

```bash
# macOS: .app and .dmg
chmod +x desktop/build_macos.sh
./desktop/build_macos.sh
```

| Platform | Output | Notes |
| :--- | :--- | :--- |
| Windows | `desktop/dist/UsisAIn-Setup.msi`<br>`desktop/dist/UsisAIn-windows-x64.zip`<br>`desktop/dist/UsisAIn/UsisAIn.exe` | 1-Click MSI Installer with embedded custom License / EULA and uninstaller. Portable ZIP and folder executable. |
| macOS | `desktop/dist/UsisAIn-macos-universal.zip`<br>`desktop/dist/UsisAIn.app`<br>`desktop/dist/UsisAIn-macOS.dmg` | Universal cross-platform package with `run_macos.sh`. Native `.app` bundle and DMG disk image built via `build_macos.sh`. |

### Browser detection and extension install flow

1. **Detection:** checks running browser processes (`chrome.exe`, `msedge.exe`, `brave.exe`, `opera.exe`, `firefox.exe`, `Safari`). If several are running, shows a picker with your default preselected. If none are running, reads the system default (Windows Registry `UserChoice\ProgId` or macOS LaunchServices).
2. **Prompt:** offers **Add**, **Not now**, or **Don't ask again** (saved in `%LOCALAPPDATA%\UsisAIn\config.json` or `~/Library/Application Support/UsisAIn/config.json`). Skipped automatically if the extension is already installed.
3. **Install:**
   - **Chromium:** opens the extensions page with a one-click "Copy folder path" for Load unpacked.
   - **Firefox:** opens `about:debugging#/runtime/this-firefox` and provides the Gecko manifest path.
   - **Safari:** opens the bundled Safari Web Extension wrapper.

### Data isolation and updates

Databases, uploaded scans, and `.env` credentials live in `%LOCALAPPDATA%\UsisAIn\app` (Windows) or `~/Library/Application Support/UsisAIn/app` (macOS). Rebuilding the launcher updates the bundled code while preserving your database, vector store, and API keys.

---

## Troubleshooting

| Problem | Fix |
| :--- | :--- |
| **Connection error in extension or web app** | Make sure the backend is running on `http://localhost:8000`. |
| **Ollama offline** | Run `ollama serve` and check models with `ollama list`. |
| **Search errors in Step 3** | Verify `GOOGLE_API_KEY` and `GOOGLE_CSE_ID` in `.env`. |
| **Cloud key test fails** | Re-enter the key in **AI Settings** and click **Test Key** for a diagnostic response. |
| **"Tesseract not found" warning** | Tesseract is optional. Image verification automatically uses multimodal vision models instead. |