from fastapi import APIRouter, UploadFile, File, Form, Depends
from usisain_backend.extraction.extraction import cleanup_file
from usisain_backend.orchestration.pipeline import run_pipeline_blocking
from usisain_backend.core.config import settings
from usisain_backend.services.analysis_service import AnalysisService

router = APIRouter(prefix="/api/analyze", tags=["analyze"])


def get_service() -> AnalysisService:
    return AnalysisService()


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
    service: AnalysisService = Depends(get_service),
):
    provider, language = service.resolve_provider_and_language(provider, language)
    content = await service.prepare_content(text, file, caption)

    try:
        results = await run_pipeline_blocking(
            content, language=language, provider=provider, use_ocr=use_ocr
        )
        input_summary = (text or caption or (file.filename if file else ""))[:200]
        scan_id = service.record_scan(
            channel=channel,
            content_type=content.get("content_type"),
            results=results,
            source_url=source_url,
            input_summary=input_summary,
            language=language,
        )
        return {"scan_id": scan_id, **results}
    finally:
        cleanup_file(content.get("file_path"))
