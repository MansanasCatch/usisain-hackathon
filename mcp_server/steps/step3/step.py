import os

from mcp_server.shared.text_utils import truncate
from mcp_server.steps.base import BaseStep, Step3Input, Step3Output
from mcp_server.steps.step3.cache_writer import save_investigation_cache
from mcp_server.steps.step3.page_scraper import fetch_multiple_pages
from mcp_server.steps.step3.query_gen import generate_search_query
from mcp_server.steps.step3.rag_lookup import lookup_advisories, lookup_rag_cache
from mcp_server.steps.step3.search_client import execute_search
from mcp_server.steps.step3.source_scorer import deduplicate_sources, score_sources
from mcp_server.steps.step3.synthesis import synthesize_explanation


class Step3LegitOrFake(BaseStep):
    step_number = 3
    name = "legit_or_fake"

    async def run(self, input_data: Step3Input) -> Step3Output:
        claim = input_data.claim
        file_path = input_data.file_path
        content_type = input_data.content_type
        provider = input_data.provider
        language = input_data.language
        step1_result = input_data.step1_result
        step2_result = input_data.step2_result
        search_query = await generate_search_query(
            claim, file_path, content_type, provider, step1_result, step2_result
        )
        if not search_query or not search_query.strip():
            return Step3Output(
                score=0,
                verdict="no_claim",
                explanation="No claim or image content was provided to verify.",
                sources=[],
                cached_matches=[],
                search_error=None,
            )
        cached = lookup_rag_cache(search_query)
        advisories = lookup_advisories(search_query)
        search_results, search_error = execute_search(search_query, max_results=3)
        scored = score_sources(claim, search_results, query=search_query)
        top_sources = deduplicate_sources(scored)[:2]
        urls_to_fetch = [s["url"] for s in top_sources if s.get("url")]
        fetch_enabled = os.environ.get("STEP3_FETCH_FULL_PAGE", "False").lower() in (
            "1",
            "true",
            "yes",
        )
        page_contents = (
            fetch_multiple_pages(urls_to_fetch) if fetch_enabled and urls_to_fetch else {}
        )
        source_context_lines = []
        for s in top_sources:
            content = page_contents.get(s["url"], "")
            snippet = truncate(content, 700) if content else truncate(s["snippet"], 180)
            source_context_lines.append(
                f"- Title: {s['title']}\n  URL: {s['url']}\n  Snippet: {snippet}\n"
            )
        source_context = "\n".join(source_context_lines) or "No web sources found."
        if top_sources:
            score = round(sum((s["combined"] for s in top_sources)) / len(top_sources) * 100, 1)
        else:
            score = 15.0
        if score >= 70:
            verdict = "likely_true"
        elif score >= 45:
            verdict = "inconclusive"
        else:
            verdict = "flagged"
        if not top_sources or verdict == "flagged":
            note = "\n\nNOTE: No verified web search results corroborate this specific claim. Therefore, do NOT include any 'Sources' or 'Sources:' section and do NOT list any links or URLs in your output."
            sources_rule = "4. Do NOT include any 'Sources' section or links, since no verified web search results corroborate this claim.\n"
        else:
            note = f"\n\nOnly list from the following verified sources if they directly corroborate or refute the claim: {[s['url'] for s in top_sources]}"
            sources_rule = "4. At the end of your explanation, list the relevant, verified sources as clickable markdown links in the format:\n   - [Source Title/Domain](URL): Brief description of what this source verifies.\n"
        explanation = await synthesize_explanation(
            verdict=verdict,
            score=score,
            claim=claim,
            search_query=search_query,
            top_sources=top_sources,
            scored_sources=scored,
            cached=cached,
            advisories=advisories,
            source_context=source_context,
            sources_rule=sources_rule,
            note=note,
            file_path=file_path,
            content_type=content_type,
            provider=provider,
            language=language,
        )
        save_investigation_cache(search_query, score, verdict, top_sources)
        return Step3Output(
            score=int(score),
            verdict=verdict,
            explanation=explanation,
            sources=top_sources,
            cached_matches=cached,
            search_error=search_error,
        )
