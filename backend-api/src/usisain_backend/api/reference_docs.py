from fastapi import APIRouter, Depends, File, Form, UploadFile

from usisain_backend.services.reference_docs_service import ReferenceDocsService

router = APIRouter(prefix="/api/reference-documents", tags=["reference-documents"])


def get_service() -> ReferenceDocsService:
    return ReferenceDocsService()


@router.post("")
async def upload_reference_document(
    file: UploadFile = File(...),
    name: str = Form(...),
    category: str = Form(...),
    notes: str | None = Form(None),
    service: ReferenceDocsService = Depends(get_service),
):
    doc_id = await service.save_uploaded_document(
        file=file, name=name, category=category, notes=notes
    )
    return {"id": doc_id}


@router.get("")
def list_reference_documents(
    category: str | None = None, service: ReferenceDocsService = Depends(get_service)
):
    return service.list_documents(category=category)


@router.delete("/{doc_id}")
def delete_reference_document(doc_id: int, service: ReferenceDocsService = Depends(get_service)):
    service.delete_document(doc_id)
    return {"deleted": doc_id}
