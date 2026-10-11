from typing import Any
from mcp_server.constants import RAG_SIMILARITY_THRESHOLD
from mcp_server.services.rag import retriever


def lookup_rag_cache(query: str) -> list[dict[str, Any]]:
    return retriever.search(query, top_k=1, category="investigation")


def lookup_advisories(query: str) -> list[dict[str, Any]]:
    return retriever.search(
        query,
        top_k=2,
        min_score=RAG_SIMILARITY_THRESHOLD,
        category="reference",
    )
