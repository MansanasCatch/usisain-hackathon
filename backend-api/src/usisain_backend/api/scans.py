from fastapi import APIRouter
from ..data import db

router = APIRouter(prefix="/api/scans", tags=["scans"])


@router.get("")
def list_scans(channel: str | None = None, limit: int = 20, offset: int = 0):
    return db.get_scans(channel=channel, limit=limit, offset=offset)


@router.get("/stats/summary")
def stats_summary():
    return db.get_summary_stats()
