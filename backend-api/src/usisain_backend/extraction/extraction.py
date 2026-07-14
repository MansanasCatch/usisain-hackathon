"""extraction.py — turns whatever a client sends (raw text, an uploaded
file, a caption+image pair) into the normalized shape orchestration.pipeline
expects.  Files are written to OS temp storage and cleaned up after the
pipeline finishes (see stream.py / analyze.py)."""

import os
import tempfile
from pathlib import Path


def _save_upload(file_bytes: bytes, filename: str) -> str:
    """Save uploaded bytes to a temporary file that persists until we
    explicitly delete it (delete=False).  Returns the temp file path."""
    ext = Path(filename).suffix or ".bin"
    fd = tempfile.NamedTemporaryFile(
        delete=False, suffix=ext, prefix="usisain_"
    )
    fd.write(file_bytes)
    fd.close()
    return fd.name


def cleanup_file(file_path: str | None):
    """Remove a temp file if it exists.  Safe to call with None."""
    if file_path:
        try:
            os.unlink(file_path)
        except OSError:
            pass


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
