import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env", override=True)
try:
    import pydantic._internal._typing_extra as _te

    if not hasattr(_te, "eval_type_backport"):
        setattr(
            _te,
            "eval_type_backport",
            getattr(_te, "eval_type_lenient", getattr(_te, "eval_type", None)),
        )
except Exception:
    pass
from mcp.server.fastmcp import FastMCP

from mcp_server.tools.step1_ai_insights import generate_insight
from mcp_server.tools.step2_content_analyser import analyze_content
from mcp_server.tools.step3_legit_or_fake import check_claim
from mcp_server.tools.step4_actionable_items import generate_actions
from mcp_server.tools.step5_learnings import generate_learnings

mcp = FastMCP("usisain-pipeline")


@mcp.tool()
async def step1_ai_insights(
    content_summary: str,
    file_path: str | None = None,
    content_type: str = "text",
    provider: str = "ollama",
    language: str = "english",
    use_ocr: bool = True,
) -> dict:
    return await generate_insight(
        content_summary, file_path, content_type, provider, language, use_ocr
    )


@mcp.tool()
async def step2_content_analyser(
    file_path: str,
    content_type: str,
    provider: str = "ollama",
    language: str = "english",
    step1_result: dict | None = None,
) -> dict:
    return await analyze_content(file_path, content_type, provider, language, step1_result)


@mcp.tool()
async def step3_legit_or_fake(
    claim: str,
    file_path: str | None = None,
    content_type: str = "text",
    provider: str = "ollama",
    language: str = "english",
    step1_result: dict | None = None,
    step2_result: dict | None = None,
) -> dict:
    return await check_claim(
        claim, file_path, content_type, provider, language, step1_result, step2_result
    )


@mcp.tool()
async def step4_actionable_items(
    step1_result: dict,
    step2_result: dict,
    step3_result: dict,
    provider: str = "ollama",
    language: str = "english",
) -> dict:
    return await generate_actions(step1_result, step2_result, step3_result, provider, language)


@mcp.tool()
async def step5_learnings(
    step1_result: dict,
    step2_result: dict,
    step3_result: dict,
    provider: str = "ollama",
    language: str = "english",
) -> dict:
    return await generate_learnings(step1_result, step2_result, step3_result, provider, language)


if __name__ == "__main__":
    mcp.run()
