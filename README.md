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
│   └── web-app/            # placeholder — not built yet
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
- **`client/web-app/`** — reserved for a future full web client; empty for now.

## 3. Prerequisites (Windows)

1. **Python 3.11+**
2. **Ollama** — download from ollama.com, then:
   ```
   ollama pull qwen2.5:7b
   ```
3. **Tesseract OCR** (optional — powers OCR-based checks): https://github.com/UB-Mannheim/tesseract/wiki
4. ffmpeg isn't needed separately — `faster-whisper` bundles what it needs via PyAV.

## 4. Where to get each API key

| Key | Where to get it | Required? |
|---|---|---|
| `GOOGLE_API_KEY` | https://console.cloud.google.com/apis/credentials — enable the "Custom Search API" | Yes, for step 3 |
| `GOOGLE_CSE_ID` | https://programmablesearchengine.google.com/ — create a search engine, set it to search the entire web, copy the "Search engine ID" | Yes, for step 3 |
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey — only needed if you pass `provider=gemini` instead of the default local Ollama | Optional |
| `META_VERIFY_TOKEN` | You choose this yourself — any random string, used to verify the webhook | Yes, for the Messenger bot only |
| `META_PAGE_ACCESS_TOKEN` | https://developers.facebook.com/apps → create an app → add the "Messenger" product → generate a Page Access Token for a Page you control | Yes, for the Messenger bot only |
| `META_APP_SECRET` | Same Meta App → Settings → Basic → "App Secret" (verifies incoming webhook signatures) | Recommended, for the Messenger bot only |

## 5. One-time setup

```powershell
cd usisain
py -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

copy .env.example .env
# edit .env: GOOGLE_API_KEY, GOOGLE_CSE_ID at minimum; Messenger keys only if you're running the bot

py data\scripts\init_db.py
```

That's the entire install — one venv, one `requirements.txt`, one `.env`,
shared by the backend, the MCP server, and the Messenger bot.

## 6. Running the backend

```powershell
cd backend-api
uvicorn usisain_backend.main:app --reload --app-dir src --port 8000
```

`--app-dir src` is what lets this run without a `pyproject.toml` or
`pip install -e` — it just adds `backend-api/src` to Python's import path
for the duration of the run. Visit `http://localhost:8000` — you should
see `{"status": "ok", ...}`. Leave this running.

The MCP server (`mcp_server/server.py`) starts automatically per request
as a subprocess — you never run it directly.

## 7. Browser extension setup (desktop)

1. `chrome://extensions` → enable **Developer mode** → **Load unpacked** → select `client/browser-extension/`
2. Keep the backend running. Right-click selected text, an image, or a
   video anywhere on the web — a results panel appears bottom-right and
   fills in as each of the 5 steps completes.
3. **Known limitation:** videos served via `blob:` URLs (common on
   Facebook/Instagram/X's own players) can't be fetched by the extension.
   Direct `<video src="...mp4">` elements work fine.

## 8. Messenger bot setup (mobile)

The bot needs a **public HTTPS URL** for Meta to send webhooks to. For
local development, use ngrok:
```powershell
ngrok http 8001
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

## 9. Localization

Every request accepts a `language` field: `english`, `taglish` (the
`.env` default), `tagalog`, `cebuano`, or `ilocano`. Steps 1, 4, and 5
(the LLM-generated ones) write their output in that language; steps 2 and
3 are language-neutral. The extension currently hardcodes `taglish` in
`background.js` — change `DEFAULT_LANGUAGE` there, or wire it to a
settings UI if you want it user-configurable. The Messenger bot reads
`DEFAULT_LANGUAGE` from the shared `.env`.

## 10. Text-to-speech

`POST /api/tts?text=...&language=...` returns a `.wav` file, generated
locally via `pyttsx3` (wraps Windows' built-in SAPI5 voices — no API key,
fully offline). English quality is reliable since every Windows install
ships English voices. **Tagalog quality depends on whether a Filipino
voice pack is installed** (Windows Settings → Time & Language → Speech →
Add voices) — without one, it falls back to the default voice and will
mispronounce Tagalog text. This isn't wired into the pipeline
automatically; call it on the aggregated explanation text once analysis
finishes, from whichever client wants audio.

## 11. Troubleshooting

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
