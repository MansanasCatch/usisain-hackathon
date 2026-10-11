from fastapi import APIRouter
from usisain_backend.data import db

router = APIRouter(prefix="/api/scans", tags=["scans"])


@router.get("")
def list_scans(channel: str | None = None, limit: int = 20, offset: int = 0):
    return db.get_scans(channel=channel, limit=limit, offset=offset)


@router.get("/stats/summary")
def stats_summary():
    return db.get_summary_stats()


@router.get("/stats/trends")
def stats_trends(days: int = 30):
    return db.get_trend(days=days)


@router.delete("")
def clear_all_scans():
    count = db.clear_scans()
    return {"deleted": count}
