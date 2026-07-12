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
load_dotenv(Path(__file__).parent.parent / ".env")

from mcp.server.fastmcp import FastMCP

from tools.step1_ai_insights import generate_insight
from tools.step2_content_analyser import analyze_content
from tools.step3_legit_or_fake import check_claim
from tools.step4_actionable_items import generate_actions
from tools.step5_learnings import generate_learnings

mcp = FastMCP("usisain-pipeline")


@mcp.tool()
def step1_ai_insights(content_summary: str, provider: str = "ollama", language: str = "english") -> dict:
    """Step 1: give an initial LLM read of the content before deeper analysis.

    Args:
        content_summary: Text description of the content (claim, caption, or OCR'd text).
        provider: 'ollama' (local, default) or 'gemini' (cloud).
        language: 'english' (default), 'taglish', 'tagalog', 'cebuano', or 'ilocano'.
    """
    return generate_insight(content_summary, provider, language)


@mcp.tool()
def step2_content_analyser(file_path: str, content_type: str) -> dict:
    """Step 2: break an image or video into real / edited / AI-generated percentages.

    Args:
        file_path: Absolute path to the image or video file on disk.
        content_type: 'image' or 'video'.
    """
    return analyze_content(file_path, content_type)


@mcp.tool()
def step3_legit_or_fake(claim: str, provider: str = "ollama") -> dict:
    """Step 3: check a claim against cached prior investigations and fresh
    web search, scoring and explaining source credibility.

    Args:
        claim: The text claim to verify.
        provider: 'ollama' (local, default) or 'gemini' (cloud).
    """
    return check_claim(claim, provider)


@mcp.tool()
def step4_actionable_items(step1_result: dict, step2_result: dict, step3_result: dict,
                            provider: str = "ollama", language: str = "english") -> dict:
    """Step 4: generate concrete next-step suggestions from steps 1-3's findings."""
    return generate_actions(step1_result, step2_result, step3_result, provider, language)


@mcp.tool()
def step5_learnings(step1_result: dict, step2_result: dict, step3_result: dict,
                     provider: str = "ollama", language: str = "english") -> dict:
    """Step 5: generate educational material and source links teaching the underlying pattern."""
    return generate_learnings(step1_result, step2_result, step3_result, provider, language)


if __name__ == "__main__":
    mcp.run()  # stdio transport by default
