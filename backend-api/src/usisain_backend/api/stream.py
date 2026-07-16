"""stream.py — SSE endpoint. Streams one event per pipeline step the
instant it completes, instead of buffering the whole response.
Temp files are cleaned up after the pipeline finishes."""

import json
import traceback
from fastapi import APIRouter, UploadFile, File, Form, Request
from fastapi.responses import StreamingResponse

from ..extraction.extraction import extract_text, extract_image, extract_video, extract_post, cleanup_file
from ..orchestration.pipeline import run_pipeline
from ..data import db
from ..core.config import settings

router = APIRouter(prefix="/api/analyze", tags=["analyze"])


async def _sse_stream(request: Request, content: dict, channel: str, language: str, provider: str,
                       source_url: str | None, input_summary: str | None, use_ocr: bool = True):
    results: dict[str, dict] = {}
    try:
        async for event in run_pipeline(content, language=language, provider=provider, use_ocr=use_ocr, request=request):
            if event.status in ("completed", "error"):
                results[f"step{event.step}"] = event.result
            yield f"data: {json.dumps(event.to_dict())}\n\n"

        scan_id = db.insert_scan(
            channel=channel, content_type=content.get("content_type"), results=results,
            source_url=source_url, input_summary=input_summary, language=language,
        )
        yield f"data: {json.dumps({'done': True, 'scan_id': scan_id})}\n\n"
    except Exception as exc:
        err_msg = str(exc).strip() or f"Unexpected error: {type(exc).__name__}"
        db.insert_error(
            step=None, step_name=None,
            error_msg=err_msg, error_type="system",
            details=traceback.format_exc(),
        )
        yield f"data: {json.dumps({'error': err_msg})}\n\n"
    finally:
        # Clean up the temp file after the pipeline is done
        cleanup_file(content.get("file_path"))


@router.post("/stream")
async def analyze_stream(
    request: Request,
    text: str | None = Form(None),
    file: UploadFile | None = File(None),
    caption: str | None = Form(None),
    language: str = Form(settings.default_language),
    provider: str = Form(settings.default_llm_provider),
    source_url: str | None = Form(None),
    use_ocr: bool = Form(True),
):
    provider = (provider or settings.default_llm_provider).strip().lower()
    if provider not in ("ollama", "gemini"):
        provider = settings.default_llm_provider
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

    input_summary = (text or caption or (file.filename if file else ""))[:200]

    return StreamingResponse(
        _sse_stream(request, content, "extension", language, provider, source_url, input_summary, use_ocr),
        media_type="text/event-stream",
        status_code=202,
    )
