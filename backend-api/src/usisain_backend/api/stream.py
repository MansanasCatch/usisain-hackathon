"""stream.py — SSE endpoint. Streams one event per pipeline step the
instant it completes, instead of buffering the whole response."""

import json
from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import StreamingResponse

from ..extraction.extraction import extract_text, extract_image, extract_video, extract_post
from ..orchestration.pipeline import run_pipeline
from ..data import db
from ..core.config import settings

router = APIRouter(prefix="/api/analyze", tags=["analyze"])


async def _sse_stream(content: dict, channel: str, language: str, provider: str,
                       source_url: str | None, input_summary: str | None):
    results: dict[str, dict] = {}
    async for event in run_pipeline(content, language=language, provider=provider):
        if event.status in ("completed", "error"):
            results[f"step{event.step}"] = event.result
        yield f"data: {json.dumps(event.to_dict())}\n\n"

    scan_id = db.insert_scan(
        channel=channel, content_type=content.get("content_type"), results=results,
        source_url=source_url, input_summary=input_summary, language=language,
    )
    yield f"data: {json.dumps({'done': True, 'scan_id': scan_id})}\n\n"


@router.post("/stream")
async def analyze_stream(
    text: str | None = Form(None),
    file: UploadFile | None = File(None),
    caption: str | None = Form(None),
    language: str = Form(settings.default_language),
    provider: str = Form(settings.default_llm_provider),
    source_url: str | None = Form(None),
):
    file_bytes = await file.read() if file else None

    if file_bytes and caption is not None:
        content = extract_post(caption, file_bytes, file.filename)
    elif file_bytes:
        ext = (file.filename or "").lower()
        content = extract_video(file_bytes, file.filename, caption) if ext.endswith((".mp4", ".mov", ".webm")) \
            else extract_image(file_bytes, file.filename, caption)
    else:
        content = extract_text(text or "")

    input_summary = (text or caption or (file.filename if file else ""))[:200]

    return StreamingResponse(
        _sse_stream(content, "extension", language, provider, source_url, input_summary),
        media_type="text/event-stream",
    )
