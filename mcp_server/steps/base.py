from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Step1Input:
    content_summary: str
    file_path: str | None = None
    content_type: str = "text"
    provider: str = "ollama"
    language: str = "english"
    use_ocr: bool = True


@dataclass
class Step1Output:
    insight: str | None
    explanation: str
    ocr_text: str = ""
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = {"insight": self.insight, "explanation": self.explanation, "ocr_text": self.ocr_text}
        if self.error:
            d["error"] = self.error
        return d


@dataclass
class Step2Input:
    file_path: str
    content_type: str = "image"
    provider: str = "ollama"
    language: str = "english"
    step1_result: dict[str, Any] | None = None


@dataclass
class Step2Output:
    real_pct: float = 0.0
    edited_pct: float = 0.0
    ai_generated_pct: float = 0.0
    score: float = 0.0
    verdict: str = "authentic"
    explanation: str = ""
    applicable: bool = True
    details: dict[str, Any] = field(default_factory=dict)
    frames_analyzed: int | None = None
    duration_seconds: float | None = None
    transcript: str | None = None
    content_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        if not self.applicable:
            return {"applicable": False, "explanation": self.explanation}
        res: dict[str, Any] = {
            "applicable": self.applicable,
            "real_pct": self.real_pct,
            "edited_pct": self.edited_pct,
            "ai_generated_pct": self.ai_generated_pct,
            "score": self.score,
            "verdict": self.verdict,
            "explanation": self.explanation,
            "details": self.details,
        }
        if self.content_type:
            res["content_type"] = self.content_type
        if self.frames_analyzed is not None:
            res["frames_analyzed"] = self.frames_analyzed
        if self.duration_seconds is not None:
            res["duration_seconds"] = self.duration_seconds
        if self.transcript is not None:
            res["transcript"] = self.transcript
        return res


@dataclass
class Step3Input:
    claim: str
    file_path: str | None = None
    content_type: str = "text"
    provider: str = "ollama"
    language: str = "english"
    step1_result: dict[str, Any] | None = None
    step2_result: dict[str, Any] | None = None


@dataclass
class Step3Output:
    score: int
    verdict: str
    explanation: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    cached_matches: list[dict[str, Any]] = field(default_factory=list)
    search_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "verdict": self.verdict,
            "explanation": self.explanation,
            "sources": self.sources,
            "cached_matches": self.cached_matches,
            "search_error": self.search_error,
        }


@dataclass
class Step4Input:
    step1_result: dict[str, Any]
    step2_result: dict[str, Any]
    step3_result: dict[str, Any]
    provider: str = "ollama"
    language: str = "english"


@dataclass
class Step4Output:
    actions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {"actions": self.actions}


@dataclass
class Step5Input:
    step1_result: dict[str, Any]
    step2_result: dict[str, Any]
    step3_result: dict[str, Any]
    provider: str = "ollama"
    language: str = "english"


@dataclass
class Step5Output:
    tips: list[str]
    explanation: str
    learning_material: str
    source_links: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tips": self.tips,
            "explanation": self.explanation,
            "learning_material": self.learning_material,
            "source_links": self.source_links,
        }


class BaseStep(ABC):
    step_number: int
    name: str

    @abstractmethod
    async def run(self, input_data: Any) -> Any:
        raise NotImplementedError
