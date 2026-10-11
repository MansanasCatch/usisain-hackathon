from typing import Any

from usisain_backend.data.repositories.connection import get_db_connection


class ErrorsRepository:
    def insert(
        self,
        step: int | None,
        step_name: str | None,
        error_msg: str,
        error_type: str = "pipeline",
        details: str | None = None,
    ) -> int:
        with get_db_connection() as conn:
            cur = conn.execute(
                """INSERT INTO errors (step, step_name, error_type, error_msg, details)
                   VALUES (?, ?, ?, ?, ?)""",
                (step, step_name, error_type, error_msg, details),
            )
            return int(cur.lastrowid)

    def list_all(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        with get_db_connection() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM errors ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
            ]

    def get_stats(self) -> dict[str, Any]:
        with get_db_connection() as conn:
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

    def clear(self) -> int:
        with get_db_connection() as conn:
            cur = conn.execute("DELETE FROM errors")
            return cur.rowcount
