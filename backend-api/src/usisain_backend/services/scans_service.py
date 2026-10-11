from typing import Any

from usisain_backend.data.repositories.scans_repository import ScansRepository


class ScansService:
    def __init__(self, repo: ScansRepository | None = None):
        self.repo = repo or ScansRepository()

    def list_scans(
        self, channel: str | None = None, limit: int = 20, offset: int = 0
    ) -> list[dict[str, Any]]:
        return self.repo.get_all(channel=channel, limit=limit, offset=offset)

    def get_summary(self) -> dict[str, Any]:
        return self.repo.get_summary_stats()

    def get_trends(self, days: int = 30) -> list[dict[str, Any]]:
        return self.repo.get_trends(days=days)

    def clear(self) -> int:
        return self.repo.clear()
