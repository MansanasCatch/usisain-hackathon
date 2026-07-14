"""db.py — persistence for completed pipeline runs. Each scan stores all
5 step results as one JSON blob (raw_result_json) plus flattened columns
for fast dashboard queries."""

import sqlite3
import json
from ..core.config import settings


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    channel         TEXT NOT NULL DEFAULT 'extension',  -- 'extension' | 'messenger' | 'webapp'
    content_type    TEXT,                                -- 'text' | 'image' | 'video' | 'post'
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    source_url      TEXT,
    input_summary   TEXT,
    language        TEXT DEFAULT 'english',
    step2_score     REAL,      -- % real, for dashboard trend compatibility
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
    step        INTEGER,                                -- 1-5, or NULL for general errors
    step_name   TEXT,                                   -- e.g. 'ai_insights', 'legit_or_fake'
    error_type  TEXT NOT NULL DEFAULT 'pipeline',       -- 'pipeline' | 'api' | 'system'
    error_msg   TEXT NOT NULL,
    details     TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_errors_created_at ON errors(created_at);
"""


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA)
    print(f"Database ready at {settings.db_path}")


def insert_scan(channel: str, content_type: str, results: dict,
                 source_url: str | None = None, input_summary: str | None = None,
                 language: str = "english") -> int:
    step2 = results.get("step2", {})
    step3 = results.get("step3", {})
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO scans (channel, content_type, source_url, input_summary,
               language, step2_score, step3_verdict, raw_result_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (channel, content_type, source_url, input_summary, language,
             step2.get("score"), step3.get("verdict"), json.dumps(results)),
        )
        return cur.lastrowid


def get_scans(channel: str | None = None, limit: int = 20, offset: int = 0) -> list[dict]:
    query = "SELECT * FROM scans WHERE 1=1"
    params: list = []
    if channel:
        query += " AND channel = ?"
        params.append(channel)
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def get_summary_stats() -> dict:
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM scans").fetchone()["c"]
        by_channel = conn.execute("SELECT channel, COUNT(*) c FROM scans GROUP BY channel").fetchall()
        by_verdict = conn.execute("SELECT step3_verdict, COUNT(*) c FROM scans GROUP BY step3_verdict").fetchall()
        return {
            "total_scans": total,
            "by_channel": {r["channel"]: r["c"] for r in by_channel},
            "by_verdict": {r["step3_verdict"]: r["c"] for r in by_verdict},
        }


def get_trend(days: int = 30) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT date(created_at) AS day, channel, COUNT(*) AS c, AVG(step2_score) AS avg_score
               FROM scans
               WHERE created_at >= datetime('now', ?)
               GROUP BY day, channel
               ORDER BY day ASC""",
            (f"-{days} days",),
        ).fetchall()
        return [dict(r) for r in rows]


# ---------- reference documents ----------

def insert_reference_document(name: str, category: str, image_path: str,
                               notes: str | None = None) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO reference_documents (name, category, image_path, notes)
               VALUES (?, ?, ?, ?)""",
            (name, category, image_path, notes),
        )
        return cur.lastrowid


def get_reference_documents(category: str | None = None) -> list[dict]:
    query = "SELECT * FROM reference_documents"
    params: list = []
    if category:
        query += " WHERE category = ?"
        params.append(category)
    query += " ORDER BY uploaded_at DESC"
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def delete_reference_document(doc_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM reference_documents WHERE id = ?", (doc_id,))


# ---------- error log ----------

def insert_error(step: int | None, step_name: str | None, error_msg: str,
                 error_type: str = "pipeline", details: str | None = None) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO errors (step, step_name, error_type, error_msg, details)
               VALUES (?, ?, ?, ?, ?)""",
            (step, step_name, error_type, error_msg, details),
        )
        return cur.lastrowid


def get_errors(limit: int = 50, offset: int = 0) -> list[dict]:
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM errors ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()]


def get_error_stats() -> dict:
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM errors").fetchone()["c"]
        by_type = conn.execute(
            "SELECT error_type, COUNT(*) c FROM errors GROUP BY error_type"
        ).fetchall()
        by_step = conn.execute(
            "SELECT step_name, COUNT(*) c FROM errors WHERE step IS NOT NULL GROUP BY step_name"
        ).fetchall()
        return {
            "total_errors": total,
            "by_type": {r["error_type"]: r["c"] for r in by_type},
            "by_step": {r["step_name"]: r["c"] for r in by_step},
        }


def clear_errors() -> int:
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM errors")
        return cur.rowcount


def clear_scans() -> int:
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM scans")
        # Also reset the local RAG vector store so cached claims don't linger
        rag_store = settings.project_root / "data" / "vector_index" / "store.json"
        try:
            if rag_store.exists():
                rag_store.write_text("[]", encoding="utf-8")
        except Exception:
            pass
        return cur.rowcount
