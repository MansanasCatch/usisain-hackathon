"""
pipeline.py — the only place that knows the 5-step order.
Steps execute sequentially (1 → 2 → 3 → 4 → 5) and yield a StepEvent the
moment each one finishes, enabling progressive UI updates on the client side.
"""

import asyncio
import logging
import traceback
import uuid
from typing import AsyncGenerator
from fastapi import Request

from usisain_backend.core.config import settings
from usisain_backend.core.request_context import REQUEST_ID
from usisain_backend.orchestration.events import STEP_NAMES, StepEvent
from usisain_backend.services.mcp_client.client import call_tool
from usisain_backend.data import db

logger = logging.getLogger(__name__)

# Maps tool name -> (step number, step display name)
_STEP_INFO: dict[str, tuple[int, str]] = {
    "step1_ai_insights": (1, "ai_insights"),
    "step2_content_analyser": (2, "content_analyser"),
    "step3_legit_or_fake": (3, "legit_or_fake"),
    "step4_actionable_items": (4, "actionable_items"),
    "step5_learnings": (5, "learnings"),
}


async def _safe_call(tool_name: str, arguments: dict) -> dict:
    timeout_seconds = settings.pipeline_step_timeout_seconds
    try:
        # Wrap tool call in a configurable timeout
        result = await asyncio.wait_for(call_tool(tool_name, arguments), timeout=timeout_seconds)
        # Some tools return {"error": "..."} without raising — log those too
        if isinstance(result, dict) and result.get("error"):
            step_num, step_name = _STEP_INFO.get(tool_name, (None, tool_name))
            db.insert_error(
                step=step_num, step_name=step_name,
                error_msg=result["error"], error_type="pipeline",
                details=f"Tool: {tool_name}",
            )
        return result
    except asyncio.TimeoutError:
        step_num, step_name = _STEP_INFO.get(tool_name, (None, tool_name))
        err_msg = f"Step timed out after {timeout_seconds:.0f} seconds."
        db.insert_error(
            step=step_num, step_name=step_name,
            error_msg=err_msg, error_type="pipeline_timeout",
            details=f"Tool: {tool_name} timed out after {timeout_seconds:.0f} seconds.",
        )
        return {"error": err_msg}
    except Exception as e:
        tb = traceback.format_exc()
        logger.exception("Error calling MCP tool %s with args %s", tool_name, arguments)
        err_msg = str(e).strip() or f"Unexpected error: {type(e).__name__}"
        step_num, step_name = _STEP_INFO.get(tool_name, (None, tool_name))
        db.insert_error(
            step=step_num, step_name=step_name,
            error_msg=err_msg, error_type="pipeline",
            details=tb,
        )
        return {"error": err_msg}


def _status_for(result: dict) -> str:
    return "error" if isinstance(result, dict) and result.get("error") else "completed"


def _skip_remaining_steps(start_step: int, reason: str) -> list[StepEvent]:
    return [StepEvent(step, STEP_NAMES[step], "error", {"error": reason}) for step in range(start_step, 6)]


async def run_pipeline(content: dict, language: str = "english", provider: str = "ollama", use_ocr: bool = True, request: Request | None = None) -> AsyncGenerator[StepEvent, None]:
    """`content` is the output of the extraction layer:
    {"content_type": "text"|"image"|"video"|"post", "text": str|None, "file_path": str|None}
    """
    provider = (provider or "ollama").strip().lower()
    # Assign a unique request id for tracing LLM calls in logs
    request_id = str(uuid.uuid4())
    REQUEST_ID.set(request_id)
    print(f"INFO:     [Pipeline] request_id={request_id}", flush=True)

    text_summary = content.get("text") or ""
    file_path = content.get("file_path")
    content_type = content.get("content_type", "text")
    results: dict[str, dict] = {}

    print(f"INFO:     [Pipeline] Using provider: {provider}", flush=True)
    # ---- Step 1: AI Insights ----
    if request is not None and await request.is_disconnected():
        print("INFO:     [Pipeline] Client disconnected before Step 1. Aborting.", flush=True)
        return
    print("INFO:     [Step 1/5] Starting AI Insights...", flush=True)
    yield StepEvent(1, "ai_insights", "in_progress")

    results["step1"] = await _safe_call(
        "step1_ai_insights",
        {
            "content_summary": text_summary or "",
            "file_path": file_path,
            "content_type": content_type,
            "provider": provider,
            "language": language,
            "use_ocr": use_ocr,
        },
    )
    status1 = _status_for(results["step1"])
    print(f"INFO:     [Step 1/5] Completed AI Insights. Status: {status1}", flush=True)
    yield StepEvent(1, "ai_insights", status1, results["step1"])

    if status1 == "error":
        for event in _skip_remaining_steps(2, "Skipped because a previous step failed."):
            yield event
        return

    # ---- Step 2: Content Analyser ----
    if request is not None and await request.is_disconnected():
        print("INFO:     [Pipeline] Client disconnected before Step 2. Aborting.", flush=True)
        return
    if file_path and content_type in ("image", "video"):
        print("INFO:     [Step 2/5] Starting Content Analyser...", flush=True)
        yield StepEvent(2, "content_analyser", "in_progress")

        results["step2"] = await _safe_call(
            "step2_content_analyser", {
                "file_path": file_path,
                "content_type": content_type,
                "provider": provider,
                "language": language,
                "step1_result": results["step1"],
            },
        )
        status2 = _status_for(results["step2"])
        print(f"INFO:     [Step 2/5] Completed Content Analyser. Status: {status2}", flush=True)
        yield StepEvent(2, "content_analyser", status2, results["step2"])
        if status2 == "error":
            for event in _skip_remaining_steps(3, "Skipped because a previous step failed."):
                yield event
            return
    else:
        results["step2"] = {"applicable": False, "explanation": "Content analyser applies to images and video only."}
        print(f"INFO:     [Step 2/5] Completed Content Analyser. Status: completed", flush=True)
        yield StepEvent(2, "content_analyser", "completed", results["step2"])

    # ---- Step 3: Legit or Fake ----
    if request is not None and await request.is_disconnected():
        print("INFO:     [Pipeline] Client disconnected before Step 3. Aborting.", flush=True)
        return
    print("INFO:     [Step 3/5] Starting Authenticity...", flush=True)
    yield StepEvent(3, "legit_or_fake", "in_progress")
    claim = text_summary or content.get("caption", "") or ""
    # Inject OCR'd text from Step 1 if available to ensure we search based on all text in the image
    if results.get("step1") and results["step1"].get("ocr_text"):
        ocr_txt = results["step1"]["ocr_text"].strip()
        if ocr_txt:
            if claim.strip():
                if ocr_txt.lower() not in claim.lower():
                    claim = f"{claim}\n\n{ocr_txt}"
            else:
                claim = ocr_txt
    results["step3"] = await _safe_call(
        "step3_legit_or_fake",
        {
            "claim": claim,
            "file_path": file_path,
            "content_type": content_type,
            "provider": provider,
            "language": language,
            "step1_result": results["step1"],
            "step2_result": results["step2"],
        },
    )
    status3 = _status_for(results["step3"])
    print(f"INFO:     [Step 3/5] Completed Authenticity. Status: {status3}", flush=True)
    yield StepEvent(3, "legit_or_fake", status3, results["step3"])
    if status3 == "error":
        for event in _skip_remaining_steps(4, "Skipped because a previous step failed."):
            yield event
        return

    # ---- Steps 4 & 5: Actionable Items and Learnings ----
    common_args = {
        "step1_result": results["step1"], "step2_result": results["step2"], "step3_result": results["step3"],
        "provider": provider, "language": language,
    }

    if provider == "ollama":
        # Under local Ollama, run sequentially to avoid overloading local CPU/GPU memory and preventing timeouts
        if request is not None and await request.is_disconnected():
            print("INFO:     [Pipeline] Client disconnected before Step 4. Aborting.", flush=True)
            return
        print("INFO:     [Step 4/5] Starting Actionable Items...", flush=True)
        yield StepEvent(4, "actionable_items", "in_progress")
        results["step4"] = await _safe_call("step4_actionable_items", common_args)
        status4 = _status_for(results["step4"])
        print(f"INFO:     [Step 4/5] Completed Actionable Items. Status: {status4}", flush=True)
        yield StepEvent(4, "actionable_items", status4, results["step4"])

        if request is not None and await request.is_disconnected():
            print("INFO:     [Pipeline] Client disconnected before Step 5. Aborting.", flush=True)
            return
        print("INFO:     [Step 5/5] Starting Learnings...", flush=True)
        yield StepEvent(5, "learnings", "in_progress")
        results["step5"] = await _safe_call("step5_learnings", common_args)
        status5 = _status_for(results["step5"])
        print(f"INFO:     [Step 5/5] Completed Learnings. Status: {status5}", flush=True)
        yield StepEvent(5, "learnings", status5, results["step5"])
    else:
        # Under Gemini (cloud), run concurrently for maximum speed
        if request is not None and await request.is_disconnected():
            print("INFO:     [Pipeline] Client disconnected before concurrent Steps 4 & 5. Aborting.", flush=True)
            return
        print("INFO:     [Step 4/5] Starting Actionable Items...", flush=True)
        print("INFO:     [Step 5/5] Starting Learnings...", flush=True)
        yield StepEvent(4, "actionable_items", "in_progress")
        yield StepEvent(5, "learnings", "in_progress")

        step4_task = asyncio.create_task(_safe_call("step4_actionable_items", common_args))
        step5_task = asyncio.create_task(_safe_call("step5_learnings", common_args))

        pending = {step4_task: 4, step5_task: 5}
        while pending:
            if request is not None and await request.is_disconnected():
                print("INFO:     [Pipeline] Client disconnected during concurrent Steps 4 & 5. Cancelling pending tasks.", flush=True)
                for task in pending:
                    task.cancel()
                return
            done, _ = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                step = pending.pop(task)
                results[f"step{step}"] = task.result()
                status = _status_for(results[f"step{step}"])
                step_name = "actionable_items" if step == 4 else "learnings"
                print(f"INFO:     [Step {step}/5] Completed {step_name.replace('_', ' ').title()}. Status: {status}", flush=True)
                yield StepEvent(step, step_name, status, results[f"step{step}"])


async def run_pipeline_blocking(content: dict, language: str = "english", provider: str = "ollama", use_ocr: bool = True) -> dict:
    """Collects every event and returns one aggregated dict — used by
    clients that consume a complete response instead of streaming live UI updates."""
    results: dict[str, dict] = {}
    async for event in run_pipeline(content, language, provider, use_ocr=use_ocr):
        if event.status in ("completed", "error"):
            results[f"step{event.step}"] = event.result
    return results
