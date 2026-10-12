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
    from mcp_server.steps.step3.source_scorer import is_source_relevant
    top_sources = [s for s in top_sources if is_source_relevant(s, claim, search_query)]
    if not top_sources or verdict == "flagged":
        sources_rule = "4. Do NOT include any 'Sources' section or links, since no verified web search results corroborate this claim.\n"
        note = "\n\nNOTE: No verified web search results corroborate this specific claim. Therefore, do NOT include any 'Sources' or 'Sources:' section and do NOT list any links or URLs in your output."
        source_context = "No verified web sources corroborate this claim."

    advisory_lines = []
    for a in advisories:
        advisory_name = a.get("metadata", {}).get("name", "Unknown Source")
        advisory_lines.append(f"- {a['text']} [Source: {advisory_name}]")
    advisory_context = "\n".join(advisory_lines) or "None"
    verdict_label = {
        "likely_true": "LIKELY_TRUE (Legitimate / corroborated)",
        "inconclusive": "INCONCLUSIVE (Unverified / questionable)",
        "flagged": "FLAGGED (Unverified / lacking credible evidence)",
    }.get(verdict, verdict.upper())
    context = (
        f"Assigned Verdict: {verdict_label}\n"
        f"Credibility Score: {score}/100\n"
        f"Claim/Context: {claim or '(no text claim provided, checking the image)'}\n\n"
        f"Search query: {search_query}\n\n"
        f"Official Advisories & Reference Documents:\n{advisory_context}\n\n"
        f"Cached prior investigations:\n{chr(10).join((c['text'][:150] for c in cached)) or 'None'}\n\n"
        f"Web search results:\n{source_context}{note}"
    )
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
        if explanation:
            import re

            allowed_urls = {s["url"].rstrip("/").lower() for s in top_sources if s.get("url")}
            lines = []
            for line in explanation.splitlines():
                stripped_line = line.strip()
                lower_line = stripped_line.lower()
                found_markdown_links = re.findall(r"\[([^\]]+)\]\((https?://[^\)]+)\)", line)
                found_raw_urls = re.findall(r"(https?://[^\s\)]+)", line)
                urls_in_line = [
                    u.rstrip("/").lower() for _, u in found_markdown_links
                ] + [u.rstrip("/").lower() for u in found_raw_urls]

                if not top_sources or verdict == "flagged":
                    if (
                        found_markdown_links
                        or found_raw_urls
                        or lower_line.startswith((
                            "sources:", "source:", "* source", "- source", "sources",
                            "verified source", "the only relevant", "relevant source",
                            "* http", "- http"
                        ))
                        or "wikipedia.org/wiki/" in lower_line
                    ):
                        continue
                else:
                    if urls_in_line:
                        if not any(
                            any(allowed in u or u in allowed for allowed in allowed_urls)
                            for u in urls_in_line
                        ):
                            continue
                    if "wikipedia.org/wiki/" in lower_line and not any("wikipedia.org" in au for au in allowed_urls):
                        continue

                lines.append(line)
            explanation = "\n".join(lines).strip()

            # Safeguard: Remove any hallucinated mentions of unrelated entities
            irrelevant_entities = ["jeffrey epstein", "epstein", "mamluk", "bloons"]
            for bad_entity in irrelevant_entities:
                if bad_entity in explanation.lower() and bad_entity not in (claim + " " + search_query).lower():
                    explanation = re.sub(rf"(?i)[^.\n]*\b{re.escape(bad_entity)}\b[^.\n]*\.?", "", explanation)
            explanation = re.sub(r"\n{3,}", "\n\n", explanation).strip()
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
