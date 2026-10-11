import uuid
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from usisain_backend.data import db
from usisain_backend.core.config import settings

router = APIRouter(prefix="/api/reference-documents", tags=["reference-documents"])


@router.post("")
async def upload_reference_document(
    file: UploadFile = File(...), name: str = Form(...),
    category: str = Form(...), notes: str | None = Form(None),
):
    # Enforce maximum upload size limit server-side
    max_bytes = int(settings.max_reference_doc_size_mb * 1024 * 1024)
    contents = b""
    chunk_size = 1024 * 1024  # 1MB chunks
    
    try:
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            contents += chunk
            if len(contents) > max_bytes:
                raise HTTPException(
                    status_code=400,
                    detail=f"The selected image exceeds the maximum allowed file size of {settings.max_reference_doc_size_mb} MB. Please upload a smaller image."
                )
    finally:
        await file.close()

    dest = settings.reference_images_dir / f"{uuid.uuid4().hex}_{file.filename}"
    dest.write_bytes(contents)
    doc_id = db.insert_reference_document(name=name, category=category, image_path=str(dest), notes=notes)
    
    # Index reference document into local RAG vector store for instant semantic checking
    try:
        from mcp_server.services.rag import retriever
        retriever.add(f"Official advisory: {name}. Detail: {notes or ''}", {
            "name": name,
            "category": "reference",
            "doc_id": doc_id,
        })
    except Exception as e:
        print(f"Failed to index reference document in RAG: {e}")
        
    return {"id": doc_id}


@router.get("")
def list_reference_documents(category: str | None = None):
    return db.get_reference_documents(category=category)


@router.delete("/{doc_id}")
def delete_reference_document(doc_id: int):
    db.delete_reference_document(doc_id)
    return {"deleted": doc_id}
