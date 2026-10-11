from typing import Any

from usisain_backend.data.repositories.connection import get_db_connection


class ReferenceDocsRepository:
    def insert(self, name: str, category: str, image_path: str, notes: str | None = None) -> int:
        with get_db_connection() as conn:
            cur = conn.execute(
                """INSERT INTO reference_documents (name, category, image_path, notes)
                   VALUES (?, ?, ?, ?)""",
                (name, category, image_path, notes),
            )
            return int(cur.lastrowid)

    def list_all(self, category: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM reference_documents"
        params: list[Any] = []
        if category:
            query += " WHERE category = ?"
            params.append(category)
        query += " ORDER BY uploaded_at DESC"
        with get_db_connection() as conn:
            return [dict(r) for r in conn.execute(query, params).fetchall()]

    def delete(self, doc_id: int) -> None:
        with get_db_connection() as conn:
            conn.execute("DELETE FROM reference_documents WHERE id = ?", (doc_id,))
