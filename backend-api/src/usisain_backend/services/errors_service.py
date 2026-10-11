from typing import Any

from usisain_backend.data.repositories.errors_repository import ErrorsRepository


class ErrorsService:
    def __init__(self, repo: ErrorsRepository | None = None):
        self.repo = repo or ErrorsRepository()

    def get_errors(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        return self.repo.list_all(limit=limit, offset=offset)

    def get_stats(self) -> dict[str, Any]:
        return self.repo.get_stats()

    def clear(self) -> int:
        return self.repo.clear()
