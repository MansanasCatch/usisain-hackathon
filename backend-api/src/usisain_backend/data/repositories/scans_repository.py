import json
from typing import Any

from usisain_backend.core.config import settings
from usisain_backend.data.repositories.connection import get_db_connection


class ScansRepository:
    def insert(
        self,
        channel: str,
        content_type: str,
        results: dict[str, Any],
        source_url: str | None = None,
        input_summary: str | None = None,
        language: str = "english",
    ) -> int:
        step2 = results.get("step2", {})
        step3 = results.get("step3", {})
        with get_db_connection() as conn:
            cur = conn.execute(
                """INSERT INTO scans (channel, content_type, source_url, input_summary,
                   language, step2_score, step3_verdict, raw_result_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    channel,
                    content_type,
                    source_url,
                    input_summary,
                    language,
                    step2.get("score"),
                    step3.get("verdict"),
                    json.dumps(results),
                ),
            )
            return int(cur.lastrowid)

    def get_all(
        self, channel: str | None = None, limit: int = 20, offset: int = 0
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM scans WHERE 1=1"
        params: list[Any] = []
        if channel:
            query += " AND channel = ?"
            params.append(channel)
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with get_db_connection() as conn:
            return [dict(r) for r in conn.execute(query, params).fetchall()]

    def get_by_id(self, scan_id: int) -> dict[str, Any] | None:
        with get_db_connection() as conn:
            row = conn.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()
            return dict(row) if row else None

    def get_summary_stats(self) -> dict[str, Any]:
        with get_db_connection() as conn:
            total = conn.execute("SELECT COUNT(*) c FROM scans").fetchone()["c"]
            by_channel = conn.execute(
                "SELECT channel, COUNT(*) c FROM scans GROUP BY channel"
            ).fetchall()
            by_verdict = conn.execute(
                "SELECT step3_verdict, COUNT(*) c FROM scans GROUP BY step3_verdict"
            ).fetchall()
            return {
                "total_scans": total,
                "by_channel": {r["channel"]: r["c"] for r in by_channel},
                "by_verdict": {r["step3_verdict"]: r["c"] for r in by_verdict},
            }

    def get_trends(self, days: int = 30) -> list[dict[str, Any]]:
        with get_db_connection() as conn:
            rows = conn.execute(
                """SELECT date(created_at) AS day, channel, COUNT(*) AS c, AVG(step2_score) AS avg_score
                   FROM scans
                   WHERE created_at >= datetime('now', ?)
                   GROUP BY day, channel
                   ORDER BY day ASC""",
                (f"-{days} days",),
            ).fetchall()
            return [dict(r) for r in rows]

    def clear(self) -> int:
        with get_db_connection() as conn:
            cur = conn.execute("DELETE FROM scans")
            rag_store = settings.project_root / "data" / "vector_index" / "store.json"
            try:
                if rag_store.exists():
                    rag_store.write_text("[]", encoding="utf-8")
            except Exception:
                pass
            return cur.rowcount
