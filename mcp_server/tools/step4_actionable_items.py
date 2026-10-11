from mcp_server.steps.base import Step4Input
from mcp_server.steps.step4 import Step4ActionableItems
from mcp_server.services.llm import get_provider

_step4_runner = Step4ActionableItems()


async def generate_actions(
    step1_result: dict,
    step2_result: dict,
    step3_result: dict,
    provider: str = "ollama",
    language: str = "english",
) -> dict:
    inp = Step4Input(
        step1_result=step1_result,
        step2_result=step2_result,
        step3_result=step3_result,
        provider=provider,
        language=language,
    )
    res = await _step4_runner.run(inp)
    return res.to_dict()
