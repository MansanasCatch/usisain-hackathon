import uuid
from typing import Any
from fastapi import HTTPException, UploadFile
from usisain_backend.core.config import settings
from usisain_backend.data.repositories.reference_docs_repository import (
    ReferenceDocsRepository,
)


class ReferenceDocsService:
    def __init__(self, repo: ReferenceDocsRepository | None = None):
        self.repo = repo or ReferenceDocsRepository()

    async def save_uploaded_document(
        self,
        file: UploadFile,
        name: str,
        category: str,
        notes: str | None = None,
    ) -> int:
        max_bytes = int(settings.max_reference_doc_size_mb * 1024 * 1024)
        contents = b""
        chunk_size = 1024 * 1024

        try:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                contents += chunk
                if len(contents) > max_bytes:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"The selected image exceeds the maximum allowed file size of "
                            f"{settings.max_reference_doc_size_mb} MB. Please upload a smaller image."
                        ),
                    )
        finally:
            await file.close()

        dest = (
            settings.reference_images_dir
            / f"{uuid.uuid4().hex}_{file.filename}"
        )
        dest.write_bytes(contents)
        doc_id = self.repo.insert(
            name=name,
            category=category,
            image_path=str(dest),
            notes=notes,
        )

        try:
            from mcp_server.services.rag import retriever

            retriever.add(
                f"Official advisory: {name}. Detail: {notes or ''}",
                {
                    "name": name,
                    "category": "reference",
                    "doc_id": doc_id,
                },
            )
        except Exception:
            pass

        return doc_id

    def list_documents(
        self, category: str | None = None
    ) -> list[dict[str, Any]]:
        return self.repo.list_all(category=category)

    def delete_document(self, doc_id: int) -> None:
        self.repo.delete(doc_id)
