"""errors.py — API endpoints for the error log / error catcher history."""

from fastapi import APIRouter
from ..data import db

router = APIRouter(prefix="/api/errors", tags=["errors"])


@router.get("")
def list_errors(limit: int = 50, offset: int = 0):
    return db.get_errors(limit=limit, offset=offset)


@router.get("/stats")
def error_stats():
    return db.get_error_stats()


@router.delete("")
def clear_all_errors():
    count = db.clear_errors()
    return {"deleted": count}
