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
