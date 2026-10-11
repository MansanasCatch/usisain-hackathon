from mcp_server.services.llm.factory import get_provider
from mcp_server.steps.base import Step2Input
from mcp_server.steps.step2 import Step2ContentAnalyser, compute_verdict, format_static_explanation

__all__ = [
    "analyze_content",
    "analyze_image",
    "analyze_video",
    "get_provider",
    "compute_verdict",
    "format_static_explanation",
]

_step2_runner = Step2ContentAnalyser()


def _verdict(real: float, edited: float, ai_gen: float) -> str:
    return compute_verdict(real, edited, ai_gen)


def _explain(real: float, edited: float, ai_gen: float, signals: dict) -> str:
    return format_static_explanation(real, edited, ai_gen, signals)


async def analyze_image(
    image_path: str,
    provider: str = "ollama",
    language: str = "english",
    step1_result: dict | None = None,
) -> dict:
    inp = Step2Input(
        file_path=image_path,
        content_type="image",
        provider=provider,
        language=language,
        step1_result=step1_result,
    )
    res = await _step2_runner.run(inp)
    return res.to_dict()


async def analyze_video(
    video_path: str,
    max_frames: int = 24,
    provider: str = "ollama",
    language: str = "english",
    step1_result: dict | None = None,
) -> dict:
    inp = Step2Input(
        file_path=video_path,
        content_type="video",
        provider=provider,
        language=language,
        step1_result=step1_result,
    )
    res = await _step2_runner.run(inp)
    return res.to_dict()


async def analyze_content(
    file_path: str,
    content_type: str,
    provider: str = "ollama",
    language: str = "english",
    step1_result: dict | None = None,
) -> dict:
    inp = Step2Input(
        file_path=file_path,
        content_type=content_type,
        provider=provider,
        language=language,
        step1_result=step1_result,
    )
    res = await _step2_runner.run(inp)
    return res.to_dict()
