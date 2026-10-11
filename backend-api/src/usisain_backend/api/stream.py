import json
import traceback

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import StreamingResponse

from usisain_backend.data.repositories.errors_repository import ErrorsRepository
from usisain_backend.extraction.extraction import cleanup_file
from usisain_backend.orchestration.pipeline import run_pipeline
from usisain_backend.services.analysis_service import AnalysisService

router = APIRouter(prefix="/api/analyze", tags=["analyze"])
_errors_repo = ErrorsRepository()


def get_service() -> AnalysisService:
    return AnalysisService()


async def _sse_stream(
    request: Request,
    content: dict,
    channel: str,
    language: str,
    provider: str,
    source_url: str | None,
    input_summary: str | None,
    use_ocr: bool,
    service: AnalysisService,
):
    results: dict[str, dict] = {}
    try:
        async for event in run_pipeline(
            content, language=language, provider=provider, use_ocr=use_ocr, request=request
        ):
            if event.status in ("completed", "error"):
                results[f"step{event.step}"] = event.result
            yield f"data: {json.dumps(event.to_dict())}\n\n"
        scan_id = service.record_scan(
            channel=channel,
            content_type=content.get("content_type"),
            results=results,
            source_url=source_url,
            input_summary=input_summary,
            language=language,
        )
        yield f"data: {json.dumps({'done': True, 'scan_id': scan_id})}\n\n"
    except Exception as exc:
        err_msg = str(exc).strip() or f"Unexpected error: {type(exc).__name__}"
        _errors_repo.insert(
            step=None,
            step_name=None,
            error_msg=err_msg,
            error_type="system",
            details=traceback.format_exc(),
        )
        yield f"data: {json.dumps({'error': err_msg})}\n\n"
    finally:
        cleanup_file(content.get("file_path"))


@router.post("/stream")
async def analyze_stream(
    request: Request,
    text: str | None = Form(None),
    file: UploadFile | None = File(None),
    caption: str | None = Form(None),
    language: str = Form("english"),
    provider: str | None = Form(None),
    source_url: str | None = Form(None),
    use_ocr: bool = Form(True),
    service: AnalysisService = Depends(get_service),
):
    provider, language = service.resolve_provider_and_language(provider, language)
    content = await service.prepare_content(text, file, caption)
    input_summary = (text or caption or (file.filename if file else ""))[:200]
    return StreamingResponse(
        _sse_stream(
            request=request,
            content=content,
            channel="extension",
            language=language,
            provider=provider,
            source_url=source_url,
            input_summary=input_summary,
            use_ocr=use_ocr,
            service=service,
        ),
        media_type="text/event-stream",
        status_code=202,
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
