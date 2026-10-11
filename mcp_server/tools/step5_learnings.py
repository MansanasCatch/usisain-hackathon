from mcp_server.steps.base import Step5Input
from mcp_server.steps.step5 import Step5Learnings
from mcp_server.services.llm import get_provider
from mcp_server.services.search import google_search

_step5_runner = Step5Learnings()


async def generate_learnings(
    step1_result: dict,
    step2_result: dict,
    step3_result: dict,
    provider: str = "ollama",
    language: str = "english",
) -> dict:
    inp = Step5Input(
        step1_result=step1_result,
        step2_result=step2_result,
        step3_result=step3_result,
        provider=provider,
        language=language,
    )
    res = await _step5_runner.run(inp)
    return res.to_dict()
