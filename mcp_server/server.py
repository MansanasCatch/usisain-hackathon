"""
server.py — MCP server exposing the 5 pipeline steps as tools over stdio.

Run standalone for a quick manual test:
    py server.py
Or let the backend spawn it automatically (see
backend-api/src/usisain_backend/services/mcp_client/client.py) — that's how
it runs in normal operation, you don't need to start this by hand.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env", override=True)
try:
    import pydantic._internal._typing_extra as _te

    if not hasattr(_te, "eval_type_backport"):
        _te.eval_type_backport = getattr(_te, "eval_type_lenient", getattr(_te, "eval_type", None))
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
def step1_ai_insights(
    content_summary: str,
    file_path: str = None,
    content_type: str = "text",
    provider: str = "ollama",
    language: str = "english",
    use_ocr: bool = True,
) -> dict:
    return generate_insight(content_summary, file_path, content_type, provider, language, use_ocr)


@mcp.tool()
def step2_content_analyser(
    file_path: str,
    content_type: str,
    provider: str = "ollama",
    language: str = "english",
    step1_result: dict = None,
) -> dict:
    return analyze_content(file_path, content_type, provider, language, step1_result)


@mcp.tool()
def step3_legit_or_fake(
    claim: str,
    file_path: str = None,
    content_type: str = "text",
    provider: str = "ollama",
    language: str = "english",
    step1_result: dict = None,
    step2_result: dict = None,
) -> dict:
    return check_claim(
        claim, file_path, content_type, provider, language, step1_result, step2_result
    )


@mcp.tool()
def step4_actionable_items(
    step1_result: dict,
    step2_result: dict,
    step3_result: dict,
    provider: str = "ollama",
    language: str = "english",
) -> dict:
    return generate_actions(step1_result, step2_result, step3_result, provider, language)


@mcp.tool()
def step5_learnings(
    step1_result: dict,
    step2_result: dict,
    step3_result: dict,
    provider: str = "ollama",
    language: str = "english",
) -> dict:
    return generate_learnings(step1_result, step2_result, step3_result, provider, language)


if __name__ == "__main__":
    mcp.run()
