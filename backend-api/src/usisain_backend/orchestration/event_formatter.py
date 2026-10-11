from typing import Any
from usisain_backend.orchestration.events import STEP_NAMES, StepEvent


def format_step_event(
    step: int,
    name: str | None = None,
    status: str = "completed",
    result: dict[str, Any] | None = None,
) -> StepEvent:
    step_name = name or STEP_NAMES.get(step, f"step{step}")
    return StepEvent(step, step_name, status, result)


def skip_remaining_steps(start_step: int, reason: str) -> list[StepEvent]:
    return [
        StepEvent(step, STEP_NAMES[step], "error", {"error": reason})
        for step in range(start_step, 6)
    ]


def format_sse_payload(event: StepEvent) -> dict[str, Any]:
    return {
        "event": "step",
        "data": event.to_json(),
    }
