from typing import Any

from mcp_server.services.rag import retriever


def save_investigation_cache(
    query: str, score: float, verdict: str, top_sources: list[dict[str, Any]]
) -> None:
    top_url = top_sources[0]["url"] if top_sources else None
    retriever.add(
        query, {"score": score, "verdict": verdict, "top_url": top_url, "category": "investigation"}
    )
