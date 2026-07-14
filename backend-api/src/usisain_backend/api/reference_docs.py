import uuid
from fastapi import APIRouter, UploadFile, File, Form
from ..data import db
from ..core.config import settings

router = APIRouter(prefix="/api/reference-documents", tags=["reference-documents"])


@router.post("")
async def upload_reference_document(
    file: UploadFile = File(...), name: str = Form(...),
    category: str = Form(...), notes: str | None = Form(None),
):
    dest = settings.reference_images_dir / f"{uuid.uuid4().hex}_{file.filename}"
    dest.write_bytes(await file.read())
    doc_id = db.insert_reference_document(name=name, category=category, image_path=str(dest), notes=notes)
    return {"id": doc_id}


@router.get("")
def list_reference_documents(category: str | None = None):
    return db.get_reference_documents(category=category)


@router.delete("/{doc_id}")
def delete_reference_document(doc_id: int):
    db.delete_reference_document(doc_id)
    return {"deleted": doc_id}
