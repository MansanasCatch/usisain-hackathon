from mcp_server.steps.base import Step1Input
from mcp_server.steps.step1 import Step1AIInsights
from mcp_server.services.llm import get_provider

_step1_runner = Step1AIInsights()


async def generate_insight(
    content_summary: str,
    file_path: str | None = None,
    content_type: str = "text",
    provider: str = "ollama",
    language: str = "english",
    use_ocr: bool = True,
) -> dict:
    inp = Step1Input(
        content_summary=content_summary,
        file_path=file_path,
        content_type=content_type,
        provider=provider,
        language=language,
        use_ocr=use_ocr,
    )
    res = await _step1_runner.run(inp)
    return res.to_dict()
