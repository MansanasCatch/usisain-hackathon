from typing import Any
from usisain_backend.data.repositories.connection import get_db_connection
from usisain_backend.data.repositories.scans_repository import ScansRepository
from usisain_backend.data.repositories.reference_docs_repository import (
    ReferenceDocsRepository,
)
from usisain_backend.data.repositories.errors_repository import ErrorsRepository

SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    channel         TEXT NOT NULL DEFAULT 'extension',
    content_type    TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    source_url      TEXT,
    input_summary   TEXT,
    language        TEXT DEFAULT 'english',
    step2_score     REAL,
    step3_verdict   TEXT,
    raw_result_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_scans_channel    ON scans(channel);
CREATE INDEX IF NOT EXISTS idx_scans_created_at ON scans(created_at);
CREATE INDEX IF NOT EXISTS idx_scans_verdict    ON scans(step3_verdict);

CREATE TABLE IF NOT EXISTS reference_documents (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL,
    image_path  TEXT NOT NULL,
    uploaded_at TEXT NOT NULL DEFAULT (datetime('now')),
    notes       TEXT
);

CREATE TABLE IF NOT EXISTS errors (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    step        INTEGER,
    step_name   TEXT,
    error_type  TEXT NOT NULL DEFAULT 'pipeline',
    error_msg   TEXT NOT NULL,
    details     TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_errors_created_at ON errors(created_at);
"""

_scans_repo = ScansRepository()
_ref_docs_repo = ReferenceDocsRepository()
_errors_repo = ErrorsRepository()


def get_connection():
    return get_db_connection()


def init_db() -> None:
    with get_db_connection() as conn:
        conn.executescript(SCHEMA)


def insert_scan(
    channel: str,
    content_type: str,
    results: dict[str, Any],
    source_url: str | None = None,
    input_summary: str | None = None,
    language: str = "english",
) -> int:
    return _scans_repo.insert(
        channel=channel,
        content_type=content_type,
        results=results,
        source_url=source_url,
        input_summary=input_summary,
        language=language,
    )


def get_scans(
    channel: str | None = None, limit: int = 20, offset: int = 0
) -> list[dict[str, Any]]:
    return _scans_repo.get_all(channel=channel, limit=limit, offset=offset)


def get_summary_stats() -> dict[str, Any]:
    return _scans_repo.get_summary_stats()


def get_trend(days: int = 30) -> list[dict[str, Any]]:
    return _scans_repo.get_trends(days=days)


def insert_reference_document(
    name: str, category: str, image_path: str, notes: str | None = None
) -> int:
    return _ref_docs_repo.insert(
        name=name, category=category, image_path=image_path, notes=notes
    )


def get_reference_documents(category: str | None = None) -> list[dict[str, Any]]:
    return _ref_docs_repo.list_all(category=category)


def delete_reference_document(doc_id: int) -> None:
    _ref_docs_repo.delete(doc_id)


def insert_error(
    step: int | None,
    step_name: str | None,
    error_msg: str,
    error_type: str = "pipeline",
    details: str | None = None,
) -> int:
    return _errors_repo.insert(
        step=step,
        step_name=step_name,
        error_msg=error_msg,
        error_type=error_type,
        details=details,
    )


def get_errors(limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    return _errors_repo.list_all(limit=limit, offset=offset)


def get_error_stats() -> dict[str, Any]:
    return _errors_repo.get_stats()


def clear_errors() -> int:
    return _errors_repo.clear()


def clear_scans() -> int:
    return _scans_repo.clear()
