from mcp_server.services.llm.factory import get_provider
from mcp_server.services.rag import retriever
from mcp_server.services.search import google_search
from mcp_server.steps.base import Step3Input
from mcp_server.steps.step3 import (
    Step3LegitOrFake,
)
from mcp_server.steps.step3 import (
    generate_search_query as _generate_search_query_impl,
)
from mcp_server.steps.step3 import (
    score_sources as _score_sources_impl,
)
from mcp_server.steps.step3.page_scraper import fetch_page_content

__all__ = [
    "check_claim",
    "generate_search_query",
    "get_provider",
    "google_search",
    "fetch_page_content",
    "retriever",
]

_step3_runner = Step3LegitOrFake()


def _score_sources(claim: str, results: list[dict]) -> list[dict]:
    return _score_sources_impl(claim, results)


async def generate_search_query(
    claim: str,
    file_path: str | None = None,
    content_type: str = "text",
    provider: str = "ollama",
    step1_result: dict | None = None,
    step2_result: dict | None = None,
) -> str:
    return await _generate_search_query_impl(
        claim, file_path, content_type, provider, step1_result, step2_result
    )


async def check_claim(
    claim: str,
    file_path: str | None = None,
    content_type: str = "text",
    provider: str = "ollama",
    language: str = "english",
    step1_result: dict | None = None,
    step2_result: dict | None = None,
) -> dict:
    inp = Step3Input(
        claim=claim,
        file_path=file_path,
        content_type=content_type,
        provider=provider,
        language=language,
        step1_result=step1_result,
        step2_result=step2_result,
    )
    res = await _step3_runner.run(inp)
    return res.to_dict()
