"""
webhook.py — the Messenger entry point. A user forwards a suspicious
message/image/video to your Page, this receives it, calls the exact same
backend pipeline the browser extension uses, and replies with each step's
result as a separate chat message.

Setup: see README for creating the Meta App, getting a Page Access Token,
and configuring the webhook URL (ngrok for local testing).

Run with:
    uvicorn webhook:app --reload --port 8001
"""

import os
import hmac
import hashlib
import requests
from fastapi import FastAPI, Request, Response, HTTPException

from messenger_client import send_text, send_typing_on, download_attachment
from formatters import format_step_messages

VERIFY_TOKEN = os.environ.get("META_VERIFY_TOKEN")
APP_SECRET = os.environ.get("META_APP_SECRET")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
DEFAULT_LANGUAGE = os.environ.get("DEFAULT_LANGUAGE", "taglish")

app = FastAPI(title="UsisAIn Messenger Bot")


@app.get("/webhook")
def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return Response(content=challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verification failed")


def _verify_signature(body: bytes, signature_header: str | None) -> bool:
    if not APP_SECRET or not signature_header:
        return not APP_SECRET  # allow through only if no secret is configured (local dev)
    expected = "sha256=" + hmac.new(APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


@app.post("/webhook")
async def receive_webhook(request: Request):
    body = await request.body()
    if not _verify_signature(body, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(status_code=403, detail="Invalid signature")

    payload = await request.json()
    for entry in payload.get("entry", []):
        for event in entry.get("messaging", []):
            sender_id = event.get("sender", {}).get("id")
            message = event.get("message")
            if sender_id and message:
                await _handle_message(sender_id, message)

    return {"status": "ok"}


async def _handle_message(sender_id: str, message: dict) -> None:
    send_typing_on(sender_id)

    text = message.get("text")
    attachments = message.get("attachments", [])

    file_bytes = None
    filename = None
    if attachments:
        attachment = attachments[0]
        att_type = attachment.get("type")  # 'image' | 'video' | 'file'
        url = attachment.get("payload", {}).get("url")
        if url and att_type in ("image", "video"):
            file_bytes = download_attachment(url)
            filename = f"attachment.{'mp4' if att_type == 'video' else 'jpg'}"

    form_data = {
        "channel": "messenger", "language": DEFAULT_LANGUAGE, "source_url": f"messenger:{sender_id}",
    }
    if file_bytes:
        form_data["caption"] = text or ""
        files = {"file": (filename, file_bytes)}
    else:
        form_data["text"] = text or ""
        files = None

    try:
        resp = requests.post(f"{BACKEND_URL}/api/analyze", data=form_data, files=files, timeout=180)
        resp.raise_for_status()
        results = resp.json()
    except Exception as e:
        send_text(sender_id, f"Sorry, something went wrong analyzing that: {e}")
        return

    for chat_message in format_step_messages(results):
        send_text(sender_id, chat_message)
