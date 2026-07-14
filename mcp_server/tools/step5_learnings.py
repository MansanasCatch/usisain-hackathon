from services.llm.gemini_client import get_provider
from services.search import google_search

LEARNING_QUERY_GEN_PROMPT = (
    "You are an educator specialized in digital literacy and fraud prevention. "
    "Given a short summary of a scam or misinformation check, write one search query (3-6 words) "
    "that will find credible educational materials, official guides, or learning resources. "
    "Output ONLY the query, with no quotes, preamble, or formatting."
)

SYSTEM_PROMPT_TEMPLATE = (
    "You are an educator teaching digital literacy. Given the context of checked content and the System Verdict:\n"
    "Explain the GENERAL PATTERN behind this type of content and how users can recognize it themselves next time in 2-3 sentences:\n"
    "   - If System Verdict is LIKELY_TRUE (LEGIT), explain the pattern of authentic, credible public facts or news, and how to verify them using official websites or reputable media.\n"
    "   - If System Verdict is FLAGGED (FAKE) or INCONCLUSIVE (QUESTIONABLE), explain the common pattern behind this scam or misinformation, why it succeeds (e.g., emotional appeal, clickbait), and how users can spot the red flags next time.\n"
    "CRITICAL: Do NOT invent, recommend, or list any links, resource URLs, or markdown links in your response text.\n"
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
        f"System Verdict: {verdict.upper()}\n"
        f"AI insight: {insight}\n"
        f"{step2_info}"
    )
    
    # 2. Get verified sources from Step 3 if available, to ensure they are related to the context
    top_sources = []
    if step3_result and step3_result.get("sources"):
        top_sources = step3_result["sources"][:2]

    # If no verified sources are found in Step 3, search for educational fact-check/literacy resources
    if not top_sources:
        search_query = ""
        if provider != "gemini":
            try:
                search_query = llm.complete(LEARNING_QUERY_GEN_PROMPT, context_summary, max_tokens=15)
                if search_query:
                    search_query = search_query.strip().replace('"', '').replace("'", "")
            except Exception:
                pass

        if not search_query:
            verdict_term = "scam fake news fact check" if verdict in ("flagged", "inconclusive") else "credible source news"
            search_query = f"{verdict_term} guide digital media literacy"

        search_results = []
        try:
            # Prefer official, educational, and wikipedia domains for learning materials
            query_filter = f"{search_query} site:gov.ph OR site:edu.ph OR site:wikipedia.org OR site:factcheck.org"
            search_results = google_search.search(query_filter, max_results=1)
            if not search_results:
                search_results = google_search.search(search_query, max_results=1)
        except Exception:
            pass
        
        from shared.text_utils import domain_trust
        scored_sources = []
        for r in search_results:
            trust = domain_trust(r["url"])
            # Only include high-trust domains or specifically trusted domains to avoid unrelated spam
            if trust >= 0.6 or any(d in r["url"] for d in ["wikipedia.org", "factcheck.org", "gov.ph", "edu.ph"]):
                scored_sources.append({
                    **r,
                    "combined": trust
                })
        scored_sources = sorted(scored_sources, key=lambda s: s["combined"], reverse=True)
        top_sources = scored_sources[:2]

    # Default fallback to verified social weather reports and digital literacy page if still empty
    if not top_sources:
        top_sources = [
            {
                "title": "SWS Official Social Weather Reports",
                "url": "https://sws.org.ph/social-weather-report-net"
            },
            {
                "title": "FactCheck.org Resources",
                "url": "https://www.factcheck.org/"
            }
        ]

    from shared.text_utils import truncate
    source_context_lines = []
    for s in top_sources:
        url = s.get("url", "")
        snippet_or_content = truncate(s.get("snippet") or s.get("title") or "", 150)
        source_context_lines.append(
            f"- Title: {s.get('title')}\n"
            f"  URL: {url}\n"
            f"  Webpage Content: {snippet_or_content}\n"
        )
    source_context = "\n".join(source_context_lines)
    
    # 5. Build final context for the LLM
    final_context = (
        f"System Verdict: {verdict.upper()}\n"
        f"AI insight: {insight}\n"
        f"{step2_info}"
    )

    system_prompt = SYSTEM_PROMPT_TEMPLATE
    if language in LANGUAGE_INSTRUCTIONS:
        system_prompt = f"{SYSTEM_PROMPT_TEMPLATE} {LANGUAGE_INSTRUCTIONS[language]}"

    try:
        material = llm.complete(system_prompt, final_context, max_tokens=150)
        
        # Clean up any potential markdown links from LLM
        if material:
            lines = []
            for line in material.splitlines():
                if "[" in line and "](" in line:
                    continue
                if line.strip().lower().startswith(("recommended resource", "recommended resources", "resource", "- resource", "* resource")):
                    continue
                lines.append(line)
            material = "\n".join(lines).strip()
            
        # Append verified sources programmatically in Python
        if top_sources:
            material = material.strip() + "\n\n**Recommended Resources:**\n"
            for s in top_sources:
                material += f"- [{s['title']}]({s['url']})\n"
    except Exception as e:
        material = f"Make sure to verify information before sharing. Learn more about media literacy from trusted official sites. (Learnings unavailable: {e})"
        
    tips = [line.strip("-•1234567890. ").strip() for line in material.splitlines() if line.strip()]
    source_links = [s["url"] for s in top_sources if s.get("url")]
    
    return {"tips": tips, "explanation": material, "learning_material": material, "source_links": source_links}

