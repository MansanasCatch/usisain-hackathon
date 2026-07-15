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
- **`client/browser-extension/`** — right-click text/images/video to
  analyze; results stream in live via a panel injected into the page.
- **`client/messenger_bot/`** — a user forwards a suspicious message/
  image/video to your Facebook Page; the bot replies with each step's
  result as a chat message.
- **`client/web-app/`** — plain HTML/JS/CSS, no build step. Served
  directly by the backend at `/app` (analyze page) and `/app/dashboard`
  (history, trends, reference document manager) — no separate server needed.

## 3. Prerequisites (Windows)

1. **Python 3.12
  Download Here: https://www.python.org/downloads/release/python-3120/
  Choose Windows installer (64-bit)
2. **Ollama** — install from \installers\OllamaSetup.exe or download from https://ollama.com/download/windows, then:

Using CMD Run: 
   ```
   ollama pull moondream
   ollama pull llama3.2:1b
   ```
3. **Tesseract OCR** :install from \installers\tesseract-ocr-w64-setup-5.5.0.20241111.exe or download from https://github.com/UB-Mannheim/tesseract/wiki
Choose tesseract-ocr-w64-setup-5.5.0.20241111.exe (64 bit)

## 4. Where to get each API key

## Search Engine
| `GOOGLE_API_KEY` | https://console.cloud.google.com/apis/credentials — enable the "Custom Search API" |
| `GOOGLE_CSE_ID` | https://programmablesearchengine.google.com/ — create a search engine, set it to search the entire web, copy the "Search engine ID" |

## Gemini LLM (Optional if you want to use Gemini instead of Ollama)
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey — only needed if you pass `provider=gemini` instead of the default local Ollama |

## Messenger bot (For Mobile Users)
| `META_VERIFY_TOKEN` | You choose this yourself — any random string, used to verify the webhook |
| `META_PAGE_ACCESS_TOKEN` | https://developers.facebook.com/apps → create an app → add the "Messenger" product → generate a Page Access Token for a Page you control | 
| `META_APP_SECRET` | Same Meta App → Settings → Basic → "App Secret" (verifies incoming webhook signatures) |

## 5. One-time setup

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

## 6. Running the application

```powershell
set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass 
.\run.bat
```

The MCP tools (`mcp_server/tools/`) run **in-process** inside the backend —
no separate process is spawned. You never run `server.py` directly.

## 7. Browser extension setup (desktop)

1. `chrome://extensions` → enable **Developer mode** → **Load unpacked** → select `client/browser-extension/`
2. Keep the backend running. Right-click selected text, an image, or a
   video anywhere on the web — a results panel appears bottom-right and
   fills in as each of the 5 steps completes.
3. **Known limitation:** videos served via `blob:` URLs (common on
   Facebook/Instagram/X's own players) can't be fetched by the extension.
   Direct `<video src="...mp4">` elements work fine.

## 8. Web app

With the backend running, just open **`http://localhost:8000/app`** —
nothing else to install or start.

- **Analyze page** (`/app`) — paste text, or upload an image/video, or
  submit a combined caption + image ("post" mode). Pick a language, hit
  Analyze, and watch each of the 5 steps fill in live as it completes —
  same streaming behavior as the extension's panel, just as a full page.
- **Dashboard** (`/app/dashboard`) — three tabs:
  - *Overview*: total scans, a 30-day trend chart by channel, verdict breakdown.
  - *Scan history*: filterable table across all channels (extension,
    Messenger, web app); click a row for the full structured result.
  - *Reference documents*: upload verified "known good" images (receipts,
    IDs) under a category — stored via `/api/reference-documents`, ready
    for a future step 2 enhancement that compares new uploads against them.

## 9. Messenger bot setup (mobile)

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

## 10. Localization

Every request accepts a `language` field: `english`, `taglish` (the
`.env` default), `tagalog`, `cebuano`, `bisaya`, or `ilocano`. Steps 1, 4, and 5
(the LLM-generated ones) write their output in that language; steps 2 and
3 are language-neutral. The extension currently hardcodes `taglish` in
`background.js` — change `DEFAULT_LANGUAGE` there, or wire it to a
settings UI if you want it user-configurable. The Messenger bot reads
`DEFAULT_LANGUAGE` from the shared `.env`.

## 11. Text-to-speech

`POST /api/tts?text=...&language=...` returns a `.wav` file, generated
locally via `pyttsx3` (wraps Windows' built-in SAPI5 voices — no API key,
fully offline). English quality is reliable since every Windows install
ships English voices. **Tagalog quality depends on whether a Filipino
voice pack is installed** (Windows Settings → Time & Language → Speech →
Add voices) — without one, it falls back to the default voice and will
mispronounce Tagalog text. This isn't wired into the pipeline
automatically; call it on the aggregated explanation text once analysis
finishes, from whichever client wants audio.

## 12. Troubleshooting

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
