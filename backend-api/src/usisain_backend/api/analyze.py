"""analyze.py — non-streaming endpoint. Used by clients that prefer
a single aggregated JSON response rather than live SSE streaming.
Temp files are cleaned up after the pipeline finishes."""

import os
from fastapi import APIRouter, UploadFile, File, Form

from usisain_backend.extraction.extraction import extract_text, extract_image, extract_video, extract_post, cleanup_file
from usisain_backend.orchestration.pipeline import run_pipeline_blocking
from usisain_backend.data import db
from usisain_backend.core.config import settings

router = APIRouter(prefix="/api/analyze", tags=["analyze"])


@router.post("")
async def analyze(
    text: str | None = Form(None),
    file: UploadFile | None = File(None),
    caption: str | None = Form(None),
    language: str = Form(settings.default_language),
    provider: str | None = Form(None),
    channel: str = Form("webapp"),
    source_url: str | None = Form(None),
    use_ocr: bool = Form(True),
):
    default_provider = os.environ.get("DEFAULT_LLM_PROVIDER", "ollama").strip().lower()
    provider = (provider or default_provider).strip().lower()
    if provider not in ("ollama", "gemini", "grok"):
        provider = default_provider
    # Ollama only supports English — enforce server-side
    if provider == "ollama" and language.strip().lower() != "english":
        language = "english"
    file_bytes = await file.read() if file else None

    if file_bytes and caption is not None:
        content = extract_post(caption, file_bytes, file.filename)
    elif file_bytes:
        ext = (file.filename or "").lower()
        content = extract_video(file_bytes, file.filename, caption) if ext.endswith((".mp4", ".mov", ".webm")) \
            else extract_image(file_bytes, file.filename, caption)
    else:
        content = extract_text(text or "")

    try:
        results = await run_pipeline_blocking(content, language=language, provider=provider, use_ocr=use_ocr)

        input_summary = (text or caption or (file.filename if file else ""))[:200]
        scan_id = db.insert_scan(
            channel=channel, content_type=content.get("content_type"), results=results,
            source_url=source_url, input_summary=input_summary, language=language,
        )
        return {"scan_id": scan_id, **results}
    finally:
        # Clean up the temp file after the pipeline is done
        cleanup_file(content.get("file_path"))
