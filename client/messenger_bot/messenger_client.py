"""messenger_client.py — thin wrapper around Meta's Messenger Send API.
Docs: https://developers.facebook.com/docs/messenger-platform/send-messages
"""

import os
from pathlib import Path
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

GRAPH_API_VERSION = "v21.0"
PAGE_ACCESS_TOKEN = os.environ.get("META_PAGE_ACCESS_TOKEN")


def _send(recipient_id: str, payload: dict) -> None:
    if not PAGE_ACCESS_TOKEN:
        raise RuntimeError("META_PAGE_ACCESS_TOKEN not set — see README for setup.")
    requests.post(
        f"https://graph.facebook.com/{GRAPH_API_VERSION}/me/messages",
        params={"access_token": PAGE_ACCESS_TOKEN},
        json={"recipient": {"id": recipient_id}, **payload},
        timeout=15,
    ).raise_for_status()


def send_text(recipient_id: str, text: str) -> None:
    # Messenger caps text messages at 2000 chars — split long step explanations.
    for i in range(0, len(text), 1900):
        _send(recipient_id, {"message": {"text": text[i:i + 1900]}})


def send_typing_on(recipient_id: str) -> None:
    _send(recipient_id, {"sender_action": "typing_on"})


def download_attachment(url: str) -> bytes:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.content
