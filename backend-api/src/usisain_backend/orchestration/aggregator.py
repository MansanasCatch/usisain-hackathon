from typing import Any
from usisain_backend.orchestration.events import StepEvent


def aggregate_pipeline_events(
    events: list[StepEvent],
) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for event in events:
        if event.status in ("completed", "error"):
            results[f"step{event.step}"] = event.result or {}
    return results
