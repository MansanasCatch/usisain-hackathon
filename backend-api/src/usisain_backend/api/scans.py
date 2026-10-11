from fastapi import APIRouter, Depends

from usisain_backend.services.scans_service import ScansService

router = APIRouter(prefix="/api/scans", tags=["scans"])


def get_service() -> ScansService:
    return ScansService()


@router.get("")
def list_scans(
    channel: str | None = None,
    limit: int = 20,
    offset: int = 0,
    service: ScansService = Depends(get_service),
):
    return service.list_scans(channel=channel, limit=limit, offset=offset)


@router.get("/stats/summary")
def stats_summary(service: ScansService = Depends(get_service)):
    return service.get_summary()


@router.get("/stats/trends")
def stats_trends(days: int = 30, service: ScansService = Depends(get_service)):
    return service.get_trends(days=days)


@router.delete("")
def clear_all_scans(service: ScansService = Depends(get_service)):
    count = service.clear()
    return {"deleted": count}
