from typing import Any

from mcp_server.services.rag import retriever


def save_investigation_cache(
    query: str, score: float, verdict: str, top_sources: list[dict[str, Any]]
) -> None:
    # Only cache verified, high-confidence investigations with legitimate sources
    if not top_sources or verdict != "likely_true" or score < 65.0:
        return
    top_url = top_sources[0].get("url")
    if not top_url:
        return
    retriever.add(
        query, {"score": score, "verdict": verdict, "top_url": top_url, "category": "investigation"}
    )
