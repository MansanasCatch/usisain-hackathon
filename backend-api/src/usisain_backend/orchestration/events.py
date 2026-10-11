from dataclasses import asdict, dataclass
from typing import Any, Literal

Status = Literal["pending", "in_progress", "completed", "error"]
STEP_NAMES = {
    1: "ai_insights",
    2: "content_analyser",
    3: "legit_or_fake",
    4: "actionable_items",
    5: "learnings",
}


@dataclass
class StepEvent:
    step: int
    name: str
    status: Status
    result: dict[str, Any] | None = None

    def to_dict(self) -> dict:
        return asdict(self)
