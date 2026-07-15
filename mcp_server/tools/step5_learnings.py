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


def is_related(result: dict, query: str, verdict: str) -> bool:
    title = result.get("title", "").lower()
    snippet = result.get("snippet", "").lower()
    url = result.get("url", "").lower()
    
    # Check for obvious ad/spam/malicious links in url
    if any(spam in url for spam in ["adclick", "doubleclick", "promoted", "sponsor", "clickbank"]):
        return False
        
    # Get keywords from the query (words longer than 3 characters, excluding very common terms)
    stopwords = {"guide", "digital", "media", "literacy", "fact", "check", "news", "scam", "fake", "resource", "resources"}
    query_words = [w.strip("?,.:;\"'()").lower() for w in query.split()]
    keywords = [w for w in query_words if len(w) > 3 and w not in stopwords]
    
    # If query is too short or has no keywords after filtering, use all non-short query words
    if not keywords:
        keywords = [w for w in query_words if len(w) > 3]
        
    if not keywords:
        return True # Fallback if query contains only very short words
        
    # We want at least one keyword or part of a keyword to match the title or snippet or URL
    # Or, if it's a known educational site, it's fine
    if any(d in url for d in ["wikipedia.org", "factcheck.org", "gov.ph", "edu.ph"]):
        return True
        
    for kw in keywords:
        if kw in title or kw in snippet or kw in url:
            return True
            
    return False


def deduplicate_sources(sources: list[dict]) -> list[dict]:
    seen_urls = set()
    seen_titles = set()
    unique_sources = []
    for s in sources:
        url = s.get("url", "").strip()
        title = s.get("title", "").strip().lower()
        if not url:
            continue
        # Normalize URL to avoid minor differences (like trailing slash, query params, http vs https)
        norm_url = url.lower().split('?')[0].rstrip('/')
        if norm_url.startswith("http://"):
            norm_url = "https://" + norm_url[7:]
        
        # Deduplicate URL and Title
        if norm_url not in seen_urls and title not in seen_titles:
            seen_urls.add(norm_url)
            seen_titles.add(title)
            unique_sources.append(s)
    return unique_sources


def generate_learnings(step1_result: dict, step2_result: dict, step3_result: dict,
                       provider: str = "ollama", language: str = "english") -> dict:
    llm = get_provider(provider)
    
    # 1. Distill key facts from previous steps — keep concise for fast LLM response
    verdict = step3_result.get("verdict", "unknown")
    insight = (step1_result.get("insight") or "")[:200]
    step3_exp = (step3_result.get("explanation") or "")[:300]
    
    step2_applicable = step2_result.get("applicable", True)
    step2_info = ""
    if step2_applicable:
        step2_info = (
            f"Content analysis: real={step2_result.get('real_pct') or 0}%, "
            f"edited={step2_result.get('edited_pct') or 0}%, "
            f"AI-generated={step2_result.get('ai_generated_pct') or 0}%.\n"
        )
    
    # Generate search query for educational materials
    search_query = ""
    try:
        search_query = llm.complete(LEARNING_QUERY_GEN_PROMPT, f"Verdict: {verdict}\nInsight: {insight}", max_tokens=30)
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
        search_results = google_search.search(query_filter, max_results=3)
    except Exception:
        pass

    if not search_results:
        try:
            search_results = google_search.search(search_query, max_results=3)
        except Exception:
            pass

    from shared.text_utils import domain_trust
    scored_sources = []
    for r in search_results:
        trust = domain_trust(r["url"])
        if is_related(r, search_query, verdict):
            # Only include high-trust domains or specifically trusted domains to avoid unrelated spam
            if trust >= 0.4 or any(d in r["url"] for d in ["wikipedia.org", "factcheck.org", "gov.ph", "edu.ph"]):
                scored_sources.append({
                    **r,
                    "combined": trust
                })

    # If no results found via Google Search, fallback to Step 3's sources (if any and if relevant)
    if not scored_sources and step3_result and step3_result.get("sources"):
        for s in step3_result["sources"]:
            if is_related(s, search_query, verdict):
                scored_sources.append({
                    **s,
                    "combined": 0.5
                })

    scored_sources = sorted(scored_sources, key=lambda s: s["combined"], reverse=True)
    top_sources = deduplicate_sources(scored_sources)[:2]

    # Default fallback to generic digital literacy pages if still empty
    if not top_sources:
        top_sources = [
            {
                "title": "FactCheck.org — How to Spot Fake News",
                "url": "https://www.factcheck.org/2016/11/how-to-spot-fake-news/"
            },
            {
                "title": "DICT Philippines — Digital Literacy Resources",
                "url": "https://dict.gov.ph/"
            }
        ]

    # 3. Build final context for the LLM — include Step 3 explanation for contextual grounding
    final_context = (
        f"System Verdict: {verdict.upper()}\n"
        f"Content Summary: {insight}\n"
        f"{step2_info}"
        f"Fact-check Result: {step3_exp}\n"
    )

    system_prompt = SYSTEM_PROMPT_TEMPLATE
    if language in LANGUAGE_INSTRUCTIONS:
        system_prompt = f"{SYSTEM_PROMPT_TEMPLATE} {LANGUAGE_INSTRUCTIONS[language]}"

    try:
        material = llm.complete(system_prompt, final_context, max_tokens=512)
        
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

