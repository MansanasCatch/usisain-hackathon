import os
import tempfile
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from PIL import Image

from mcp_server.tools.step1_ai_insights import generate_insight
from mcp_server.tools.step2_content_analyser import analyze_image
from mcp_server.tools.step3_legit_or_fake import check_claim
from mcp_server.tools.step4_actionable_items import generate_actions
from mcp_server.tools.step5_learnings import generate_learnings
from usisain_backend.orchestration.pipeline import run_pipeline_blocking


@pytest.mark.asyncio
async def test_step1_characterization():
    mock_provider = MagicMock()
    mock_provider.complete = AsyncMock(return_value="Neutral summary of content.")
    with patch("mcp_server.steps.step1.step.get_provider", return_value=mock_provider), \
         patch("mcp_server.tools.step1_ai_insights.get_provider", return_value=mock_provider):
        res = await generate_insight("Sample claim text", content_type="text")
        assert "insight" in res
        assert "explanation" in res
        assert "ocr_text" in res
        assert res["insight"] == "Neutral summary of content."


@pytest.mark.asyncio
async def test_step2_characterization():
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
        img = Image.new("RGB", (64, 64), color="red")
        img.save(tf.name)
        img_path = tf.name

    try:
        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value="Visual signals look consistent.")
        with patch("mcp_server.steps.step2.step.get_provider", return_value=mock_provider), \
             patch("mcp_server.tools.step2_content_analyser.get_provider", return_value=mock_provider):
            res = await analyze_image(img_path)
            assert "real_pct" in res
            assert "edited_pct" in res
            assert "ai_generated_pct" in res
            assert "verdict" in res
            assert "explanation" in res
            assert "score" in res
    finally:
        if os.path.exists(img_path):
            os.remove(img_path)


@pytest.mark.asyncio
async def test_step3_characterization():
    mock_provider = MagicMock()
    mock_provider.complete = AsyncMock(return_value="The claim is supported by news sources.")
    mock_search = [
        {"title": "GMA News Fact Check", "url": "https://gmanetwork.com/news/1", "snippet": "Official report confirmed."}
    ]
    with patch("mcp_server.steps.step3.synthesis.get_provider", return_value=mock_provider), \
         patch("mcp_server.steps.step3.query_gen.get_provider", return_value=mock_provider), \
         patch("mcp_server.tools.step3_legit_or_fake.get_provider", return_value=mock_provider), \
         patch("mcp_server.steps.step3.search_client.google_search.search", return_value=mock_search), \
         patch("mcp_server.tools.step3_legit_or_fake.google_search", return_value=mock_search), \
         patch("mcp_server.steps.step3.page_scraper.fetch_page_content", return_value="Full verified article text."), \
         patch("mcp_server.tools.step3_legit_or_fake.fetch_page_content", return_value="Full verified article text."), \
         patch("mcp_server.steps.step3.rag_lookup.retriever.search", return_value=[]), \
         patch("mcp_server.tools.step3_legit_or_fake.retriever.search", return_value=[]), \
         patch("mcp_server.steps.step3.cache_writer.retriever.add", return_value=None), \
         patch("mcp_server.tools.step3_legit_or_fake.retriever.add", return_value=None):
        res = await check_claim("Confirmed news report")
        assert "score" in res
        assert "verdict" in res
        assert "explanation" in res
        assert "sources" in res
        assert "cached_matches" in res


@pytest.mark.asyncio
async def test_step4_characterization():
    mock_provider = MagicMock()
    mock_provider.complete = AsyncMock(return_value="1. Verify from official accounts.\n2. Do not forward unconfirmed claims.")
    with patch("mcp_server.steps.step4.step.get_provider", return_value=mock_provider), \
         patch("mcp_server.tools.step4_actionable_items.get_provider", return_value=mock_provider):
        step1_res = {"insight": "A claim about cash prizes"}
        step2_res = {"applicable": False}
        step3_res = {"verdict": "flagged", "score": 25, "explanation": "No credible source."}
        res = await generate_actions(step1_res, step2_res, step3_res)
        assert "actions" in res
        assert isinstance(res["actions"], list)
        assert len(res["actions"]) >= 1


@pytest.mark.asyncio
async def test_step5_characterization():
    mock_provider = MagicMock()
    mock_provider.complete = AsyncMock(return_value="Be wary of urgent messages promising cash.")
    mock_search = [
        {"title": "BSP Security Advisory", "url": "https://bsp.gov.ph/advisory", "snippet": "Central bank advisory."}
    ]
    with patch("mcp_server.steps.step5.step.get_provider", return_value=mock_provider), \
         patch("mcp_server.tools.step5_learnings.get_provider", return_value=mock_provider), \
         patch("mcp_server.steps.step5.step.google_search.search", return_value=mock_search), \
         patch("mcp_server.tools.step5_learnings.google_search", return_value=mock_search):
        step1_res = {"insight": "Cash prize claim"}
        step2_res = {"applicable": False}
        step3_res = {"verdict": "flagged", "score": 20, "explanation": "Fraudulent"}
        res = await generate_learnings(step1_res, step2_res, step3_res)
        assert "tips" in res
        assert "explanation" in res
        assert "learning_material" in res
        assert "source_links" in res


@pytest.mark.asyncio
async def test_pipeline_blocking_characterization():
    async def mock_call(tool_name, arguments):
        if "step1" in tool_name:
            return {"insight": "Mock insight", "explanation": "Mock insight", "ocr_text": ""}
        if "step2" in tool_name:
            return {"applicable": False}
        if "step3" in tool_name:
            return {"score": 85, "verdict": "likely_true", "explanation": "Verified"}
        if "step4" in tool_name:
            return {"actions": ["Action 1", "Action 2"]}
        if "step5" in tool_name:
            return {"tips": ["Tip 1"], "explanation": "Learn 1", "learning_material": "Learn 1", "source_links": []}
        return {}

    with patch("usisain_backend.orchestration.pipeline.call_tool", side_effect=mock_call):
        results = await run_pipeline_blocking({"content_type": "text", "text": "Hello world"})
        assert "step1" in results
        assert "step2" in results
        assert "step3" in results
        assert "step4" in results
        assert "step5" in results
