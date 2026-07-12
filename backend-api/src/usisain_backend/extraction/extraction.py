"""extraction.py — turns whatever a client sends (raw text, an uploaded
file, a caption+image pair) into the normalized shape orchestration.pipeline
expects. Kept deliberately simple — heavy lifting (OCR, frame sampling)
happens inside the pipeline steps themselves, not here."""

import uuid
from pathlib import Path

from ..core.config import settings


def _save_upload(file_bytes: bytes, filename: str) -> str:
    ext = Path(filename).suffix or ".bin"
    dest = settings.uploads_dir / f"{uuid.uuid4().hex}{ext}"
    dest.write_bytes(file_bytes)
    return str(dest)


def extract_text(text: str) -> dict:
    return {"content_type": "text", "text": text.strip(), "file_path": None}


def extract_image(file_bytes: bytes, filename: str, caption: str | None = None) -> dict:
    path = _save_upload(file_bytes, filename)
    return {"content_type": "image", "text": caption, "file_path": path}


def extract_video(file_bytes: bytes, filename: str, caption: str | None = None) -> dict:
    path = _save_upload(file_bytes, filename)
    return {"content_type": "video", "text": caption, "file_path": path}


def extract_post(caption: str | None, file_bytes: bytes | None, filename: str | None) -> dict:
    """Combined caption + image/video, e.g. from the browser extension's
    'Analyze this post' action or a forwarded Messenger post."""
    if file_bytes and filename:
        ext = Path(filename).suffix.lower()
        content_type = "video" if ext in (".mp4", ".mov", ".webm", ".avi") else "image"
        path = _save_upload(file_bytes, filename)
        return {"content_type": content_type, "text": caption, "file_path": path, "caption": caption}
    return {"content_type": "text", "text": caption or "", "file_path": None}
