import os

import cv2

from mcp_server.prompts.step3_prompts import (
    LANGUAGE_INSTRUCTIONS,
    SECURITY_GUARDRAIL,
    SYNTHESIS_PROMPT_TEMPLATE,
)
from mcp_server.services.llm import get_provider


async def synthesize_explanation(
    verdict: str,
    score: float,
    claim: str,
    search_query: str,
    top_sources: list[dict],
    scored_sources: list[dict],
    cached: list[dict],
    advisories: list[dict],
    source_context: str,
    sources_rule: str,
    note: str,
    file_path: str | None = None,
    content_type: str = "text",
    provider: str = "ollama",
    language: str = "english",
) -> str:
    advisory_lines = []
    for a in advisories:
        advisory_name = a.get("metadata", {}).get("name", "Unknown Source")
        advisory_lines.append(f"- {a['text']} [Source: {advisory_name}]")
    advisory_context = "\n".join(advisory_lines) or "None"
    context = f"System Verdict: {verdict.upper()} (based on credibility score of {score}/100)\nClaim/Context: {claim or '(no text claim provided, checking the image)'}\n\nSearch query: {search_query}\n\nOfficial Advisories & Reference Documents:\n{advisory_context}\n\nCached prior investigations:\n{chr(10).join((c['text'][:150] for c in cached)) or 'None'}\n\nWeb search results:\n{source_context}{note}"
    temp_frame_path = None
    image_to_pass = None
    if file_path and os.path.exists(file_path) and (provider != "ollama"):
        if content_type == "image":
            image_to_pass = file_path
        elif content_type == "video":
            try:
                cap = cv2.VideoCapture(file_path)
                ok, frame = cap.read()
                if ok:
                    temp_dir = os.path.dirname(file_path)
                    temp_frame_path = os.path.join(temp_dir, "_temp_video_factcheck_frame.jpg")
                    cv2.imwrite(temp_frame_path, frame)
                    image_to_pass = temp_frame_path
                cap.release()
            except Exception:
                pass
    system_prompt = SYNTHESIS_PROMPT_TEMPLATE.format(sources_rule=sources_rule)
    lang_key = (language or "english").strip().lower()
    lang_inst = LANGUAGE_INSTRUCTIONS.get(lang_key, LANGUAGE_INSTRUCTIONS.get("english", ""))
    if lang_inst:
        system_prompt = f"{system_prompt} {lang_inst}"
    system_prompt = f"{system_prompt} {SECURITY_GUARDRAIL}"
    llm = get_provider(provider)
    try:
        explanation = await llm.complete(
            system_prompt, context, image_path=image_to_pass, max_tokens=512
        )
        if not top_sources and explanation:
            lines = []
            for line in explanation.splitlines():
                if "[" in line and "](" in line:
                    continue
                if (
                    line.strip()
                    .lower()
                    .startswith(("sources:", "source:", "- source", "* source", "sources"))
                ):
                    continue
                lines.append(line)
            explanation = "\n".join(lines).strip()
    except Exception as e:
        explanation = f"Found {len(scored_sources)} source(s) with average credibility score {score}/100. (LLM explanation unavailable: {e})"
    finally:
        if temp_frame_path and os.path.exists(temp_frame_path):
            try:
                os.remove(temp_frame_path)
            except Exception:
                pass
    if not explanation or explanation.strip() in ("0", "None", ".", "null"):
        if verdict == "likely_true":
            explanation = "The content aligns with available credible records and verified information."
        elif verdict == "inconclusive":
            explanation = "The content could not be independently corroborated by reliable sources. Treat with caution."
        else:
            explanation = "The claim lacks credible evidence or corroboration from official sources and has been flagged for potential misinformation."
    return explanation
