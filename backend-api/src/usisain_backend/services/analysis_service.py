import os
from typing import Any
from fastapi import UploadFile
from usisain_backend.extraction.extraction import (
    extract_text,
    extract_image,
    extract_video,
    extract_post,
)
from usisain_backend.data.repositories.scans_repository import ScansRepository


class AnalysisService:
    def __init__(self, scans_repo: ScansRepository | None = None):
        self.scans_repo = scans_repo or ScansRepository()

    def resolve_provider_and_language(
        self, provider: str | None, language: str
    ) -> tuple[str, str]:
        default_provider = (
            os.environ.get("DEFAULT_LLM_PROVIDER", "ollama").strip().lower()
        )
        resolved_provider = (provider or default_provider).strip().lower()
        if resolved_provider not in ("ollama", "gemini", "grok"):
            resolved_provider = default_provider

        resolved_language = language
        if resolved_provider == "ollama" and resolved_language.strip().lower() != "english":
            resolved_language = "english"

        return resolved_provider, resolved_language

    async def prepare_content(
        self,
        text: str | None,
        file: UploadFile | None,
        caption: str | None,
    ) -> dict[str, Any]:
        file_bytes = await file.read() if file else None

        if file_bytes and caption is not None:
            return extract_post(caption, file_bytes, file.filename)
        elif file_bytes:
            ext = (file.filename or "").lower()
            if ext.endswith((".mp4", ".mov", ".webm")):
                return extract_video(file_bytes, file.filename, caption)
            return extract_image(file_bytes, file.filename, caption)
        return extract_text(text or "")

    def record_scan(
        self,
        channel: str,
        content_type: str | None,
        results: dict[str, Any],
        source_url: str | None,
        input_summary: str | None,
        language: str,
    ) -> int:
        return self.scans_repo.insert(
            channel=channel,
            content_type=content_type or "text",
            results=results,
            source_url=source_url,
            input_summary=input_summary,
            language=language,
        )
