"""
pipeline.py — the only place that knows the 5-step order. Everything else
(steps 1-5's actual logic) lives in mcp_server/tools/; this just calls
them in the right sequence — concurrently where steps don't depend on
each other — and yields a StepEvent the moment each one finishes, which
is what makes progressive UI updates possible on the client side.

Dependency shape:
  step 1 (AI insights) and step 2 (content analyser) are independent of
    each other — run concurrently, stream whichever finishes first.
  step 3 (legit or fake) only needs the extracted text/claim — runs after
    1 & 2 so its context is available if we want to use it later, but
    doesn't strictly depend on their output today.
  step 4 (actionable items) and step 5 (learnings) both depend on 1-3's
    results but not on each other — run concurrently.
"""

import asyncio
from typing import AsyncGenerator

from .events import StepEvent
from ..services.mcp_client.client import call_tool


async def _safe_call(tool_name: str, arguments: dict) -> dict:
    try:
        return await call_tool(tool_name, arguments)
    except Exception as e:
        return {"error": str(e)}


def _status_for(result: dict) -> str:
    return "error" if isinstance(result, dict) and result.get("error") else "completed"


async def run_pipeline(content: dict, language: str = "english", provider: str = "ollama") -> AsyncGenerator[StepEvent, None]:
    """`content` is the output of the extraction layer:
    {"content_type": "text"|"image"|"video"|"post", "text": str|None, "file_path": str|None}
    """
    text_summary = content.get("text") or ""
    file_path = content.get("file_path")
    content_type = content.get("content_type", "text")
    results: dict[str, dict] = {}

    # ---- Steps 1 & 2: concurrent ----
    yield StepEvent(1, "ai_insights", "in_progress")
    step1_task = asyncio.create_task(_safe_call(
        "step1_ai_insights",
        {"content_summary": text_summary or "(no text provided, image/video only)",
         "provider": provider, "language": language},
    ))

    step2_task = None
    if file_path and content_type in ("image", "video"):
        yield StepEvent(2, "content_analyser", "in_progress")
        step2_task = asyncio.create_task(_safe_call(
            "step2_content_analyser", {"file_path": file_path, "content_type": content_type},
        ))

    pending = {step1_task} | ({step2_task} if step2_task else set())
    while pending:
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            if task is step1_task:
                results["step1"] = task.result()
                yield StepEvent(1, "ai_insights", _status_for(results["step1"]), results["step1"])
            else:
                results["step2"] = task.result()
                yield StepEvent(2, "content_analyser", _status_for(results["step2"]), results["step2"])

    if step2_task is None:
        results["step2"] = {"applicable": False, "explanation": "Content analyser applies to images and video only."}
        yield StepEvent(2, "content_analyser", "completed", results["step2"])

    # ---- Step 3 ----
    yield StepEvent(3, "legit_or_fake", "in_progress")
    claim = text_summary or content.get("caption", "")
    results["step3"] = await _safe_call("step3_legit_or_fake", {"claim": claim, "provider": provider})
    yield StepEvent(3, "legit_or_fake", _status_for(results["step3"]), results["step3"])

    # ---- Steps 4 & 5: concurrent, both depend on 1-3 ----
    yield StepEvent(4, "actionable_items", "in_progress")
    yield StepEvent(5, "learnings", "in_progress")
    common_args = {
        "step1_result": results["step1"], "step2_result": results["step2"], "step3_result": results["step3"],
        "provider": provider, "language": language,
    }
    step4_task = asyncio.create_task(_safe_call("step4_actionable_items", common_args))
    step5_task = asyncio.create_task(_safe_call("step5_learnings", common_args))

    pending = {step4_task, step5_task}
    while pending:
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            if task is step4_task:
                results["step4"] = task.result()
                yield StepEvent(4, "actionable_items", _status_for(results["step4"]), results["step4"])
            else:
                results["step5"] = task.result()
                yield StepEvent(5, "learnings", _status_for(results["step5"]), results["step5"])


async def run_pipeline_blocking(content: dict, language: str = "english", provider: str = "ollama") -> dict:
    """Collects every event and returns one aggregated dict — used by
    channels that can't consume a stream (e.g. the Messenger bot replies
    with a sequence of chat messages instead of live UI updates)."""
    results: dict[str, dict] = {}
    async for event in run_pipeline(content, language, provider):
        if event.status in ("completed", "error"):
            results[f"step{event.step}"] = event.result
    return results
