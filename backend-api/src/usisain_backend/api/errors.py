from fastapi import APIRouter, Depends
from usisain_backend.services.errors_service import ErrorsService

router = APIRouter(prefix="/api/errors", tags=["errors"])


def get_service() -> ErrorsService:
    return ErrorsService()


@router.get("")
def list_errors(
    limit: int = 50,
    offset: int = 0,
    service: ErrorsService = Depends(get_service),
):
    return service.get_errors(limit=limit, offset=offset)


@router.get("/stats")
def error_stats(service: ErrorsService = Depends(get_service)):
    return service.get_stats()


@router.delete("")
def clear_all_errors(service: ErrorsService = Depends(get_service)):
    count = service.clear()
    return {"deleted": count}
