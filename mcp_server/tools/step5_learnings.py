from services.llm.gemini_client import get_provider
from services.search import google_search

LEARNING_QUERY_GEN_PROMPT = (
    "You are an educator specialized in digital literacy and fraud prevention. "
    "Given a short summary of a scam or misinformation check, write one search query (3-6 words) "
    "that will find credible educational materials, official guides, or learning resources. "
    "Output ONLY the query, with no quotes, preamble, or formatting."
)

SYSTEM_PROMPT = (
    "You are an educator teaching digital literacy. Given the context of checked content "
    "and a list of web search results for educational materials:\n"
    "1. Explain in 2-3 sentences the GENERAL PATTERN behind this type of content or scam, and why it succeeds. "
    "Explain how users can recognize it themselves next time.\n"
    "2. Select only the most relevant, official, and credible educational resources or guides from the search results. "
    "Do NOT return any unrelated, commercial, or generic links.\n"
    "3. List the selected resources as clickable markdown links in the format:\n"
    "   - [Resource Title/Domain](URL): What the user will learn from this resource.\n"
    "CRITICAL: Use ONLY Filipino or English letters/words. "
    "NEVER output Chinese characters or any other non-Latin script."
)

LANGUAGE_INSTRUCTIONS = {
    "taglish": "Write in casual Taglish (mix of Tagalog and English). Use only Filipino and English words. NO Chinese characters.",
    "tagalog": "Isulat sa Tagalog. Gamitin lamang ang Filipino o Ingles na salita. HUWAG gumamit ng Chinese characters.",
    "cebuano": "Isulat sa Cebuano. Gamitin lamang ang Cebuano o Ingles na mga pulong. DILI mogamit og Chinese characters.",
    "ilocano": "Isulat iti Ilocano. Usaren laeng dagiti Ilocano wenno Ingles a sao. HAAN nga usaren dagiti Chinese characters.",
    "bisaya": "Isulat sa Bisaya. Gamitin lamang ang Bisaya o Ingles na mga pulong. DILI mogamit og Chinese characters.",
}


def generate_learnings(step1_result: dict, step2_result: dict, step3_result: dict,
                       provider: str = "ollama", language: str = "english") -> dict:
    llm = get_provider(provider)
    
    # 1. Distill key facts from previous steps
    verdict = step3_result.get("verdict", "unknown")
    insight = (step1_result.get("insight") or "")[:250]
    step3_exp = (step3_result.get("explanation") or "")[:250]
    
    step2_applicable = step2_result.get("applicable", True)
    step2_info = ""
    if step2_applicable:
        step2_info = (
            f"Content analysis results: real={step2_result.get('real_pct') or 0}%, "
            f"edited={step2_result.get('edited_pct') or 0}%, "
            f"AI-generated={step2_result.get('ai_generated_pct') or 0}%. "
            f"Details: {step2_result.get('explanation') or ''}\n"
        )

    context_summary = (
        f"Verdict: {verdict}\n"
        f"AI insight: {insight}\n"
        f"{step2_info}"
        f"Fact-check summary: {step3_exp}"
    )
    
    # 2. Generate search query for educational materials
    search_query = ""
    try:
        if provider == "ollama" and insight:
            # Local Ollama is faster if we use the insight text directly.
            search_query = insight[:120].strip()
        else:
            search_query = llm.complete(LEARNING_QUERY_GEN_PROMPT, context_summary)
        if search_query:
            search_query = search_query.strip().replace('"', '').replace("'", "")
    except Exception:
        pass

    if not search_query:
        search_query = f"{verdict} scam educational guide digital literacy"

    # 3. Perform search
    search_results = []
    try:
        search_results = google_search.search(search_query, max_results=1)
    except Exception:
        pass
    
    from shared.text_utils import domain_trust, truncate
    scored_sources = []
    for r in search_results:
        trust = domain_trust(r["url"])
        scored_sources.append({
            **r,
            "combined": trust
        })
    scored_sources = sorted(scored_sources, key=lambda s: s["combined"], reverse=True)
    top_sources = scored_sources[:2]
    
    source_context_lines = []
    for s in top_sources:
        url = s["url"]
        snippet_or_content = truncate(s["snippet"], 150)
        source_context_lines.append(
            f"- Title: {s['title']}\n"
            f"  URL: {url}\n"
            f"  Webpage Content: {snippet_or_content}\n"
        )
    source_context = "\n".join(source_context_lines) or "No educational sources found."
    
    # 5. Build final context for the LLM
    final_context = (
        f"Checked Content Context:\n{context_summary}\n\n"
        f"Educational Search Results:\n{source_context}"
    )
    
    system_prompt = SYSTEM_PROMPT
    if language in LANGUAGE_INSTRUCTIONS:
        system_prompt = f"{SYSTEM_PROMPT} {LANGUAGE_INSTRUCTIONS[language]}"
        
    try:
        material = llm.complete(system_prompt, final_context)
    except Exception as e:
        material = f"Make sure to verify information before sharing. Learn more about media literacy from trusted official sites. (Learnings unavailable: {e})"
        
    tips = [line.strip("-•1234567890. ").strip() for line in material.splitlines() if line.strip()]
    source_links = [s["url"] for s in top_sources if s.get("url")]
    
    return {"tips": tips, "explanation": material, "learning_material": material, "source_links": source_links}

