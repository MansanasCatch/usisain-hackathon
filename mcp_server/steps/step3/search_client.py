from typing import Any

from mcp_server.constants import SEARCH_RESULTS_LIMIT
from mcp_server.services.search import google_search


def execute_search(
    query: str, max_results: int = SEARCH_RESULTS_LIMIT
) -> tuple[list[dict[str, Any]], str | None]:
    try:
        results = google_search.search(query, max_results=max_results)
        return (results, None)
    except Exception as e:
        return ([], str(e))
