import asyncio
import uuid
from typing import AsyncGenerator

from fastapi import Request

from usisain_backend.core.request_context import REQUEST_ID
from usisain_backend.orchestration.aggregator import aggregate_pipeline_events
from usisain_backend.orchestration.event_formatter import format_step_event, skip_remaining_steps
from usisain_backend.orchestration.events import StepEvent
from usisain_backend.orchestration.step_runner import execute_step, get_step_status
from usisain_backend.services.mcp_client.client import call_tool

__all__ = ["run_pipeline", "call_tool", "aggregate_pipeline_events"]


async def _safe_call(tool_name: str, arguments: dict) -> dict:
    return await execute_step(tool_name, arguments)


def _status_for(result: dict) -> str:
    return get_step_status(result)


def _skip_remaining_steps(start_step: int, reason: str) -> list[StepEvent]:
    return skip_remaining_steps(start_step, reason)


async def run_pipeline(
    content: dict,
    language: str = "english",
    provider: str = "ollama",
    use_ocr: bool = True,
    request: Request | None = None,
) -> AsyncGenerator[StepEvent, None]:
    provider = (provider or "ollama").strip().lower()
    request_id = str(uuid.uuid4())
    REQUEST_ID.set(request_id)
    text_summary = content.get("text") or ""
    file_path = content.get("file_path")
    content_type = content.get("content_type", "text")
    results: dict[str, dict] = {}
    if request is not None and await request.is_disconnected():
        return
    yield format_step_event(1, "ai_insights", "in_progress")
    results["step1"] = await execute_step(
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
    status1 = get_step_status(results["step1"])
    yield format_step_event(1, "ai_insights", status1, results["step1"])
    if status1 == "error":
        for event in skip_remaining_steps(2, "Skipped because a previous step failed."):
            yield event
        return
    if request is not None and await request.is_disconnected():
        return
    if file_path and content_type in ("image", "video"):
        yield format_step_event(2, "content_analyser", "in_progress")
        results["step2"] = await execute_step(
            "step2_content_analyser",
            {
                "file_path": file_path,
                "content_type": content_type,
                "provider": provider,
                "language": language,
                "step1_result": results["step1"],
            },
        )
        status2 = get_step_status(results["step2"])
        yield format_step_event(2, "content_analyser", status2, results["step2"])
        if status2 == "error":
            for event in skip_remaining_steps(3, "Skipped because a previous step failed."):
                yield event
            return
    else:
        results["step2"] = {
            "applicable": False,
            "explanation": "Content analyser applies to images and video only.",
        }
        yield format_step_event(2, "content_analyser", "completed", results["step2"])
    if request is not None and await request.is_disconnected():
        return
    yield format_step_event(3, "legit_or_fake", "in_progress")
    claim = text_summary or content.get("caption", "") or ""
    if results.get("step1") and results["step1"].get("ocr_text"):
        ocr_txt = results["step1"]["ocr_text"].strip()
        if ocr_txt:
            if claim.strip():
                if ocr_txt.lower() not in claim.lower():
                    claim = f"{claim}\n\n{ocr_txt}"
            else:
                claim = ocr_txt
    results["step3"] = await execute_step(
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
    status3 = get_step_status(results["step3"])
    yield format_step_event(3, "legit_or_fake", status3, results["step3"])
    if status3 == "error":
        for event in skip_remaining_steps(4, "Skipped because a previous step failed."):
            yield event
        return
    common_args = {
        "step1_result": results["step1"],
        "step2_result": results["step2"],
        "step3_result": results["step3"],
        "provider": provider,
        "language": language,
    }
    if provider == "ollama":
        if request is not None and await request.is_disconnected():
            return
        yield format_step_event(4, "actionable_items", "in_progress")
        results["step4"] = await execute_step("step4_actionable_items", common_args)
        status4 = get_step_status(results["step4"])
        yield format_step_event(4, "actionable_items", status4, results["step4"])
        if request is not None and await request.is_disconnected():
            return
        yield format_step_event(5, "learnings", "in_progress")
        results["step5"] = await execute_step("step5_learnings", common_args)
        status5 = get_step_status(results["step5"])
        yield format_step_event(5, "learnings", status5, results["step5"])
    else:
        if request is not None and await request.is_disconnected():
            return
        yield format_step_event(4, "actionable_items", "in_progress")
        yield format_step_event(5, "learnings", "in_progress")
        step4_task = asyncio.create_task(execute_step("step4_actionable_items", common_args))
        step5_task = asyncio.create_task(execute_step("step5_learnings", common_args))
        pending = {step4_task: 4, step5_task: 5}
        while pending:
            if request is not None and await request.is_disconnected():
                for task in pending:
                    task.cancel()
                return
            done, _ = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                step = pending.pop(task)
                results[f"step{step}"] = task.result()
                status = get_step_status(results[f"step{step}"])
                step_name = "actionable_items" if step == 4 else "learnings"
                yield format_step_event(step, step_name, status, results[f"step{step}"])


async def run_pipeline_blocking(
    content: dict, language: str = "english", provider: str = "ollama", use_ocr: bool = True
) -> dict:
    events = []
    async for event in run_pipeline(content, language, provider, use_ocr=use_ocr):
        events.append(event)
    return aggregate_pipeline_events(events)
