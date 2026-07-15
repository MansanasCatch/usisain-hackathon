# UsisAIn

A local-first scam/misinformation/AI-content detection system with a
5-step educational pipeline, reachable from three client channels: a
browser extension (desktop), a Messenger bot (mobile — no app install
needed), and a web app (planned).

## 1. Project structure

```
usisain/
├── backend-api/            # FastAPI app — API gateway + orchestration
│   └── src/usisain_backend/
├── client/
│   ├── browser-extension/  # desktop — right-click to analyze
│   ├── messenger_bot/      # mobile — forward a message to your Page
│   └── web-app/            # analyze page + admin dashboard, served by backend-api at /app
├── data/                   # all runtime state, gitignored except structure
│   ├── models/             # cached local models (whisper, etc)
│   ├── reference_images/   # verified documents for comparison
│   ├── scripts/            # one-off ops scripts (init_db.py)
│   ├── uploads/
│   └── vector_index/       # local RAG cache (step 3)
├── docs/
├── mcp_server/              # the 5 pipeline steps, each an MCP tool
├── tests/
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
```

## 2. Architecture recap

```
client/browser-extension ──┐
                            ├──► backend-api (FastAPI) ──► mcp_server (5-step pipeline)
client/messenger_bot ───────┘         │                          │
                                       ▼                          ▼
                                 SQLite (data/app.db)     Ollama / Gemini, Google
                                                           Search, local RAG cache
```

- **`backend-api/`** — API gateway + orchestration. Streams step-by-step
  results over SSE (`/api/analyze/stream`) for the extension, returns one
  aggregated result (`/api/analyze`) for the Messenger bot, and generates
  speech from the final output (`/api/tts`).
- **`mcp_server/`** — the 5 pipeline steps, each an MCP tool. Spawned
  automatically by the backend — you never run this by hand.
- **`client/browser-extension/`** — right-click text/images/video or use the **Usisain Snipping** tool to analyze; results stream in live via a panel injected into the page.
- **`client/messenger_bot/`** — a user forwards a suspicious message/
  image/video to your Facebook Page; the bot replies with each step's
  result as a chat message.
- **`client/web-app/`** — plain HTML/JS/CSS, no build step. Served
  directly by the backend at `/app` (analyze page) and `/app/dashboard`
  (history, trends, reference document manager) — no separate server needed.

## 3. The 5-Step Analysis Pipeline

Each query runs sequentially through a 5-step analysis pipeline. The steps are registered as MCP tools in `mcp_server/server.py` and run in-process inside the backend API:

### Step 1: AI Insights (First-Pass Content Review)
* **Goal**: Provide an initial neutral overview and extract text/context.
* **How it works**:
  * **Text-only**: The LLM summarizes claims and flags urgent language, emotional framing, and suspicious links.
  * **Images & Video Frames**: Uses **Tesseract OCR** to extract text overlays. If using the cloud-based **Gemini** provider, it passes the image file directly to the multimodal model. If using local **Ollama**, it uses the extracted OCR text and claim text as a prompt fallback to the local text model.
  * **Usisain Snipping**: Extracts text and images within a selected region of any webpage, allowing for unified multimodal analysis.
  * **Video**: Extracts the first frame using **OpenCV** to run OCR/visual analysis.
* **Outputs**: A concise summary of the content (passed to Steps 3, 4, and 5).
* **Tech**: LLM (text/vision), Tesseract OCR, OpenCV.

### Step 2: Content Analyser (Digital Image Forensics)
* **Goal**: Analyze images and videos locally for manipulation, edits, or AI generation signals. (Skipped for text-only inputs).
* **How it works**:
  * **Error Level Analysis (ELA)**: Resaves the image at a known quality level (95%) and checks differences to find mismatched compression zones (e.g., spliced/pasted items).
  * **Frequency-Domain Analysis**: Runs a Discrete Cosine Transform (DCT) to check the ratio of high-to-low frequencies. Real camera sensors add high-frequency noise, while AI-generated images are smooth or pattern-based.
  * **EXIF Metadata**: Inspects headers for camera model information and editing software tags (Photoshop, GIMP, etc.).
  * **Percentage Breakdown**: Computes an estimated breakdown (Real% / Edited% / AI-Generated%) and assigns a verdict (`likely_authentic`, `likely_edited`, `likely_ai_generated`, or `inconclusive`).
  * **Forensic Explanation**: Under Gemini, passes the image directly; under Ollama, passes numeric signals and OCR text. Writes a user-friendly analysis explanation.
  * **Video Mode**: Samples up to 24 frames via OpenCV, runs image heuristics on each frame, and averages results. Also transcribes audio (if available) using **Faster-Whisper**.
* **Outputs**: Percentage breakdown, forensic explanation, and video transcript.
* **Tech**: NumPy + SciPy (DCT), OpenCV, Pillow, Faster-Whisper, LLM.

### Step 3: Authenticity (Fact-Check & Source Verification)
* **Goal**: Cross-reference claims against fresh web search results and local reference documents.
* **How it works**:
  * **Search Query Generation**: By default, uses a **Fast Query Generator** (`STEP3_FAST_QUERY_GEN=True`) that uses regex/heuristics to extract key entities and URLs from the claim text. If disabled or fails, falls back to an LLM-generated 3-4 word query.
  * **RAG Lookup**: Queries the local vector database for the top 1 cached prior investigation and up to 2 official advisories (reference documents) with a minimum score of 0.45.
  * **Google Search**: Sends the query to Google Custom Search API (fallback to DuckDuckGo/etc.), retrieving up to 3 results.
  * **Source Scoring & Deduplication**: Scores results based on `Domain Trust (60%)` and `Text Similarity (40%)`. Deduplicates by URL and Title, selecting the top 2 sources.
  * **Page Scraping (Optional)**: If `STEP3_FETCH_FULL_PAGE` is set to `True` in `.env`, fetches the webpage text of the top 2 sources in parallel using **ThreadPoolExecutor** and parses it using **BeautifulSoup** (up to 1,500 chars).
  * **LLM Synthesis**: The LLM receives the RAG advisories, search snippets/web text, and system verdict (`likely_true`, `inconclusive`, `flagged`). It writes an explanation and outputs the corresponding verdict mapping (`LEGIT`, `QUESTIONABLE`, `FAKE`) with verified links.
  * **Cache Storage**: Caches the query, verdict, score, and top source URL into the RAG vector store.
* **Outputs**: Credibility score (0-100), verdict (likely_true / inconclusive / flagged), and verified sources.
* **Tech**: Google Custom Search API, RAG Vector Store, BeautifulSoup, ThreadPoolExecutor, LLM.

### Step 4: Actionable Items (Personalized Security Recommendations)
* **Goal**: Provide 3-5 concrete next-step recommendations.
* **How it works**:
  * Receives Step 1 summary (capped at 180 chars), Step 2 visual breakdown, and Step 3 verdict/explanation (capped at 180 chars).
  * The LLM creates a numbered list strictly tailored to the verdict:
    * **Likely True (LEGIT)**: Promotes safe engagement and official link checking (no block/report suggestions).
    * **Flagged (FAKE)**: Recommends defensive measures (block account, unfollow, report, warn others).
    * **Inconclusive (QUESTIONABLE)**: Advises caution and further verification.
  * Privacy-preserving rules forbid the LLM from outputting specific usernames, handles (@username), or names of individuals.
* **Outputs**: A numbered list of 3-5 concrete action items.
* **Tech**: LLM.

### Step 5: Learnings (Educational Resources & Digital Literacy)
* **Goal**: Educate the user on threat patterns and provide credible digital literacy links.
* **How it works**:
  * Receives Step 3 verdict, Step 1 summary (capped at 200 chars), Step 2 visual breakdown, and Step 3 explanation (capped at 300 chars).
  * The LLM generates a 3-6 word educational query.
  * Searches Google Custom Search API (up to 3 results), filtering for official domains like `site:gov.ph`, `site:edu.ph`, `wikipedia.org`, and `factcheck.org`. Falls back to Step 3 sources if search results are empty.
  * The LLM writes a 2-3 sentence educational overview explaining the scam/threat pattern (e.g. emotional framing, clickbait). **To avoid hallucination, the LLM is prohibited from generating URLs**.
  * The Python script programmatically appends the verified educational resources as clickable markdown links at the end of the text.
* **Outputs**: 2-3 sentence educational synthesis and recommended learning links.
* **Tech**: Google Custom Search API, LLM.

---

## 4. Prerequisites (Windows)

1. **Python 3.12**
   Download Here: https://www.python.org/downloads/release/python-3120/
   Choose Windows installer (64-bit)
2. **Ollama** — install from \installers\OllamaSetup.exe or download from https://ollama.com/download/windows, then:

Using CMD Run: 
   ```
   ollama pull moondream
   ollama pull llama3.2:1b
   ollama pull nomic-embed-text
   ```
3. **Tesseract OCR** :install from \installers\tesseract-ocr-w64-setup-5.5.0.20241111.exe or download from https://github.com/UB-Mannheim/tesseract/wiki
Choose tesseract-ocr-w64-setup-5.5.0.20241111.exe (64 bit)

## 5. Where to get each API key

## Search Engine
| `GOOGLE_API_KEY` | https://console.cloud.google.com/apis/credentials — enable the "Custom Search API" |
| `GOOGLE_CSE_ID` | https://programmablesearchengine.google.com/ — create a search engine, set it to search the entire web, copy the "Search engine ID" |

## Gemini LLM (Optional if you want to use Gemini instead of Ollama)
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey — only needed if you pass `provider=gemini` instead of the default local Ollama |

## Messenger bot (For Mobile Users)
| `META_VERIFY_TOKEN` | You choose this yourself — any random string, used to verify the webhook |
| `META_PAGE_ACCESS_TOKEN` | https://developers.facebook.com/apps → create an app → add the "Messenger" product → generate a Page Access Token for a Page you control | 
| `META_APP_SECRET` | Same Meta App → Settings → Basic → "App Secret" (verifies incoming webhook signatures) |

## 6. One-time setup

```powershell
cd usisain
py -m venv venv
set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass 
venv\Scripts\activate
pip install -r requirements.txt

copy .env.example .env
# edit .env: GOOGLE_API_KEY, GOOGLE_CSE_ID at minimum; Messenger keys only if you're running the bot
 
py data\scripts\init_db.py
```

That's the entire install — one venv, one `requirements.txt`, one `.env`,
shared by the backend, the MCP server, and the Messenger bot.

## 7. Running the application

```powershell
set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass 
.\run.bat
```

The MCP tools (`mcp_server/tools/`) run **in-process** inside the backend —
no separate process is spawned. You never run `server.py` directly.

## 8. Browser extension setup (desktop)

1. `chrome://extensions` → enable **Developer mode** → **Load unpacked** → select `client/browser-extension/`
2. Keep the backend running. Right-click selected text, an image, a video, or select **Usisain Snipping** to draw a selection box anywhere on a webpage — a results panel appears bottom-right and fills in as each of the 5 steps completes.
3. **Known limitation:** videos served via `blob:` URLs (common on
   Facebook/Instagram/X's own players) can't be fetched by the extension.
   Direct `<video src="...mp4">` elements work fine.

## 9. Web app

With the backend running, just open **`http://localhost:8000/app`** —
nothing else to install or start.

- **Analyze page** (`/app`) — paste text, or upload an image/video. Pick a language, hit Analyze, and watch each of the 5 steps fill in live as it completes — same streaming behavior as the extension's panel, just as a full page.
- **Dashboard** (`/app/dashboard`) — three tabs:
  - *Overview*: total scans, a 30-day trend chart by channel, verdict breakdown.
  - *Scan history*: filterable table across all channels (extension,
    Messenger, web app); click a row for the full structured result.
  - *Reference documents*: upload official advisories, notices, or verified
    documents. These are automatically vectorized locally using `nomic-embed-text`
    and queried during Step 3 (Authenticity Check) to semantically cross-reference
    claims against official ground-truth source material.

## 10. Messenger bot setup (mobile)

The bot needs a **public HTTPS URL** for Meta to send webhooks to. For
local development, use ngrok:

1 Run \installers\ngrok.exe or Download here: https://ngrok.com/download/windows

2 Sign up for a free account here https://dashboard.ngrok.com/signup?ref=downloads

3. ngrok config add-authtoken "<YOUR_AUTHTOKEN>"

```powershell
4.ngrok http 8001
```
Copy the `https://...ngrok-free.app` URL it gives you.

1. Create a Meta App at https://developers.facebook.com/apps (type: Business)
2. Add the **Messenger** product, generate a **Page Access Token** for a
   Page you control
3. Under Messenger → Settings → Webhooks: set the callback URL to
   `https://your-ngrok-url/webhook`, set the verify token to whatever you
   put in `META_VERIFY_TOKEN`, subscribe to the `messages` field
4. Run the bot (same venv, same `.env` — no separate install):
   ```powershell
   cd client\messenger_bot
   uvicorn webhook:app --reload --port 8001
   ```
5. Message your Page (or have a test user do so) — forward a suspicious
   text, image, or video. The bot replies with each step's result as a
   separate message.

Note: while your Meta App is in development mode, only users added as
testers/admins on the app can message the Page. Submitting for App Review
is required before the general public can use it.

## 11. Localization

Every request accepts a `language` field: `english`, `taglish` (the
`.env` default), `tagalog`, `cebuano`, `bisaya`, or `ilocano`. Steps 1, 4, and 5
(the LLM-generated ones) write their output in that language; steps 2 and
3 are language-neutral. The extension currently hardcodes `taglish` in
`background.js` — change `DEFAULT_LANGUAGE` there, or wire it to a
settings UI if you want it user-configurable. The Messenger bot reads
`DEFAULT_LANGUAGE` from the shared `.env`.

## 12. Text-to-speech

`POST /api/tts?text=...&language=...` returns a `.wav` file, generated
locally via `pyttsx3` (wraps Windows' built-in SAPI5 voices — no API key,
fully offline). English quality is reliable since every Windows install
ships English voices. **Tagalog quality depends on whether a Filipino
voice pack is installed** (Windows Settings → Time & Language → Speech →
Add voices) — without one, it falls back to the default voice and will
mispronounce Tagalog text. This isn't wired into the pipeline
automatically; call it on the aggregated explanation text once analysis
finishes, from whichever client wants audio.

## 13. Troubleshooting

- **Extension panel shows a fetch error** → confirm `uvicorn` is running
  on port 8000 and nothing else is bound to that port.
- **Step 3 errors about `GOOGLE_API_KEY`** → check `.env` (project root)
  is filled in and the backend was restarted after editing it.
- **Messenger bot never receives webhooks** → the ngrok URL changes every
  restart on the free tier; update the callback URL in Meta's dashboard
  each time, or use a paid ngrok static domain.
- **Tool calls hang** → confirm `ollama list` shows your pulled model and
  `ollama serve` is running (it usually auto-starts with the desktop app).
- **Video analysis is slow** → `faster-whisper`'s first run downloads the
  model (~500MB for "small") — subsequent runs are fast. Lower
  `MAX_VIDEO_FRAMES` in `.env` if frame sampling itself is the bottleneck.
- **`pip install` fails on `opencv-python` or `faster-whisper`** → these
  need a reasonably recent `pip`; run `python -m pip install --upgrade pip`
  first if you hit build errors.
