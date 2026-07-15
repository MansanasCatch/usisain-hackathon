import os
import re
import cv2
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from services.search import google_search
from services.rag import retriever
from services.llm.gemini_client import get_provider
from shared.text_utils import domain_trust, text_similarity, truncate

QUERY_GEN_PROMPT = (
    "You are a fact-checking query generator. Given a claim, write a single search query of exactly 3 to 4 words "
    "that will verify the factual claims using search engines. Focus on key entities (e.g. SWS, Marcos, GCash, etc.). "
    "Output ONLY the raw search query, with no formatting, quotes, or preamble."
)

SYNTHESIS_PROMPT_TEMPLATE = (
    "You are a professional fact-checker explaining verification results to a general audience. "
    "Given a claim/image context, a System Verdict, and a list of web search results along with their actual page content:\n"
    "1. Explain the verification result following the System Verdict:\n"
    "   - If System Verdict is LIKELY_TRUE, explain why the content is LEGIT (likely true).\n"
    "   - If System Verdict is INCONCLUSIVE, explain why the content is QUESTIONABLE (inconclusive/unverified).\n"
    "   - If System Verdict is FLAGGED, explain why the content is flagged as FAKE (likely false) or unverified due to lack of credible supporting sources.\n"
    "2. For the relevant sources, explain specifically how their content supports or refutes the claim/image context.\n"
    "3. Filter out and ignore any sources that are unrelated, spammy, or do not support the context. Do NOT list or mention them.\n"
    "{sources_rule}"
    "5. Keep the response direct and concise (4-6 sentences total).\n"
    "CRITICAL: Do NOT invent, make up, or hallucinate any sources or URLs. Use ONLY the URLs provided in the 'Web search results' list. If no web search results are provided or if no source supports/refutes the claim, do NOT list any sources or URLs.\n"
    "CRITICAL: Use ONLY Filipino or English letters/words. "
    "NEVER output Chinese characters or any other non-Latin script."
)

LANGUAGE_INSTRUCTIONS = {
    "taglish": "Write the explanation in casual Taglish (mix of Tagalog and English). Use only Filipino and English words. NO Chinese characters.",
    "tagalog": "Isulat ang paliwanag sa Tagalog. Gamitin lamang ang Filipino o Ingles na salita. HUWAG gumamit ng Chinese characters.",
    "cebuano": "Isulat ang paliwanag sa Cebuano. Gamitin lamang ang Cebuano o Ingles na mga pulong. DILI mogamit og Chinese characters.",
    "ilocano": "Isulat ang paliwanag iti Ilocano. Usaren laeng dagiti Ilocano wenno Ingles a sao. HAAN nga usaren dagiti Chinese characters.",
    "bisaya": "Isulat ang paliwanag sa Bisaya. Gamitin lamang ang Bisaya o Ingles na mga pulong. DILI mogamit og Chinese characters.",
}


def _score_sources(claim: str, results: list[dict]) -> list[dict]:
    scored = []
    for r in results:
        trust = domain_trust(r["url"])
        similarity = text_similarity(claim, r["snippet"])
        scored.append({
            **r,
            "domain_trust": round(trust, 2),
            "text_similarity": round(similarity, 2),
            "combined": round(trust * 0.6 + similarity * 0.4, 3),
        })
    return sorted(scored, key=lambda s: s["combined"], reverse=True)


def fetch_page_content(url: str, timeout: int = 2) -> str:
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            for script in soup(["script", "style"]):
                script.decompose()
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)
            return text[:1500]
    except Exception:
        pass
    return ""


def fetch_multiple_pages(urls: list[str]) -> dict[str, str]:
    pages = {}
    with ThreadPoolExecutor(max_workers=max(1, min(3, len(urls)))) as executor:
        future_to_url = {executor.submit(fetch_page_content, url): url for url in urls}
        for future in future_to_url:
            url = future_to_url[future]
            try:
                content = future.result()
                if content:
                    pages[url] = content
            except Exception:
                pass
    return pages


def extract_fast_query(claim: str) -> str:
    if not claim:
        return ""
    
    # 1. Look for URLs and extract domain/slug components
    urls = re.findall(r'https?://(?:www\.)?([a-zA-Z0-9.-]+)(/[^\s]*)?', claim)
    if urls:
        domain, path = urls[0]
        domain_parts = [p for p in domain.split('.') if p not in ('com', 'org', 'net', 'gov', 'edu', 'ph', 'www')]
        keywords = list(domain_parts)
        if path:
            path_words = re.findall(r'[a-zA-Z0-9]+', path)
            keywords.extend([w for w in path_words if w.lower() not in ('html', 'php', 'htm', 'asp', 'jsp', 'index')])
        
        url_query = " ".join(keywords[:5])
        if url_query:
            cap_words = re.findall(r'\b[A-Z][a-z]+\b', claim)
            cap_words = [w for w in cap_words if w.lower() not in url_query.lower()]
            final_query = f"{url_query} " + " ".join(cap_words[:2])
            return final_query.strip()

    # 2. General text extraction using scoring
    # Stopwords list (Tagalog + English)
    stopwords = {
        # English
        "the", "is", "a", "and", "or", "in", "of", "to", "on", "at", "by", "for", "with", "from", 
        "this", "that", "it", "its", "are", "was", "were", "be", "been", "have", "has", "had", 
        "latest", "new", "about", "may", "can", "will", "would", "should",
        # Tagalog / Filipino
        "ang", "mga", "ng", "sa", "na", "ni", "at", "ay", "si", "para", "kay", "ng mga", "nang",
        "yung", "iyong", "itong", "bilang", "habang", "nasa", "ito", "siya", "nila", "kami", "tayo",
        "may", "mayroon", "maging", "dahil"
    }

    # Find all words in the claim
    words = re.findall(r'\b[a-zA-Z0-9-]+\b', claim)
    if not words:
        return ""

    # Determine first word of the text to avoid scoring capitalization due to sentence start
    first_word = words[0].lower()

    scored_words = []
    seen = set()
    for idx, w in enumerate(words):
        w_lower = w.lower()
        if w_lower in stopwords or len(w) < 2:
            continue
        if w_lower in seen:
            continue
        seen.add(w_lower)

        # Base score is 0
        score = 0
        # Capitalization check (skip if it is the first word of the text)
        if w[0].isupper() and w_lower != first_word:
            score += 10
        # Longer words are generally more descriptive/entities
        score += min(len(w) * 0.1, 1.0)
        # Earlier words get a slight priority
        score += max(0, (len(words) - idx) / len(words) * 0.5)

        scored_words.append((w, score, idx))

    # Sort by score descending, then take top 5
    scored_words.sort(key=lambda item: item[1], reverse=True)
    top_items = scored_words[:5]

    # Re-sort top items by their original order in the text to keep it coherent
    top_items.sort(key=lambda item: item[2])

    result_query = " ".join(item[0] for item in top_items)
    return result_query or " ".join(words[:5])


def generate_search_query(claim: str, file_path: str = None, content_type: str = "text", provider: str = "ollama", step1_result: dict = None, step2_result: dict = None) -> str:
    # Check if fast query generation is enabled
    fast_gen = os.environ.get("STEP3_FAST_QUERY_GEN", "True").lower() in ("1", "true", "yes")
    if fast_gen:
        fast_query = extract_fast_query(claim)
        if fast_query:
            return fast_query

    # Gather textual descriptions of the image/claim from prior steps
    step1_text = ""
    if step1_result:
        step1_text = step1_result.get("insight") or step1_result.get("explanation") or ""
    step2_text = ""
    if step2_result and step2_result.get("applicable") != False:
        step2_text = step2_result.get("explanation") or ""

    desc_text = f"{step1_text} {step2_text}".strip()

    # Construct context for query generation
    context_for_query = ""
    if claim:
        context_for_query += f"Accompanying Text/Claim: {claim}\n"
    if desc_text:
        context_for_query += f"Visual Description/Context: {desc_text}\n"

    context_for_query = context_for_query.strip()
    if not context_for_query:
        return ""

    llm = get_provider(provider)
    try:
        query = llm.complete(QUERY_GEN_PROMPT, context_for_query, max_tokens=30)
        query = " ".join(query.split()).strip().replace('"', '').replace("'", "")
        if query:
            return query
    except Exception:
        pass

    # Safe fallback if generation fails or query is empty
    if claim:
        return claim
    if desc_text:
        # Use first few words of the description as a query
        words = desc_text.split()
        return " ".join(words[:6])
    return ""


def check_claim(claim: str, file_path: str = None, content_type: str = "text", provider: str = "ollama", language: str = "english", step1_result: dict = None, step2_result: dict = None) -> dict:
    search_query = generate_search_query(claim, file_path, content_type, provider, step1_result, step2_result)
    
    if not search_query or not search_query.strip():
        return {
            "score": 0,
            "verdict": "no_claim",
            "explanation": "No claim or image content was provided to verify.",
            "sources": [],
            "cached_matches": [],
            "search_error": None,
        }

    # 1. RAG cache — prior investigations (category="investigation")
    cached = retriever.search(search_query, top_k=1, category="investigation")

    # 2. RAG official advisories / reference documents (category="reference")
    advisories = retriever.search(search_query, top_k=2, min_score=0.45, category="reference")

    # 2. Live web search (Google → DuckDuckGo fallback)
    search_error = None
    try:
        search_results = google_search.search(search_query, max_results=3)
    except Exception as e:
        search_results = []
        search_error = str(e)

    scored_sources = _score_sources(search_query, search_results)
    
    # Deduplicate sources before selecting top ones
    seen_urls = set()
    seen_titles = set()
    deduped_sources = []
    for s in scored_sources:
        url = s.get("url", "").strip()
        title = s.get("title", "").strip().lower()
        if not url:
            continue
        norm_url = url.lower().split('?')[0].rstrip('/')
        if norm_url.startswith("http://"):
            norm_url = "https://" + norm_url[7:]
        if norm_url not in seen_urls and title not in seen_titles:
            seen_urls.add(norm_url)
            seen_titles.add(title)
            deduped_sources.append(s)
            
    top_sources = deduped_sources[:2]

    # 3. Fetch page content for the top sources so the synthesis prompt can ignore unrelated links.
    urls_to_fetch = [s["url"] for s in top_sources if s.get("url")]
    fetch_enabled = os.environ.get("STEP3_FETCH_FULL_PAGE", "False").lower() in ("1", "true", "yes")
    page_contents = fetch_multiple_pages(urls_to_fetch) if (fetch_enabled and urls_to_fetch) else {}

    source_context_lines = []
    for s in top_sources:
        content = page_contents.get(s["url"], "")
        snippet = truncate(content, 700) if content else truncate(s["snippet"], 180)
        source_context_lines.append(
            f"- Title: {s['title']}\n"
            f"  URL: {s['url']}\n"
            f"  Snippet: {snippet}\n"
        )
    source_context = "\n".join(source_context_lines) or "No web sources found."

    # 4. Score: average combined score * 100 of top sources; default 15 when no results
    if scored_sources:
        # Average of top 2 sources to avoid score dilution from irrelevant low-ranking search results
        score = round(sum(s["combined"] for s in top_sources) / len(top_sources) * 100, 1)
    else:
        score = 15.0

    if score >= 70:
        verdict = "likely_true"
    elif score >= 45:
        verdict = "inconclusive"
    else:
        verdict = "flagged"

    note = ""
    sources_rule = ""
    if not top_sources:
        note = "\n\nNOTE: No web search results were found. Therefore, do NOT include any 'Sources' or 'Sources:' section and do NOT list any links or URLs in your output."
        sources_rule = "4. Do NOT include any 'Sources' section or links, since no web search results are available.\n"
    else:
        note = f"\n\nOnly list from the following verified sources if they are directly relevant: {[s['url'] for s in top_sources]}"
        sources_rule = (
            "4. At the end of your explanation, list the relevant, verified sources as clickable markdown links in the format:\n"
            "   - [Source Title/Domain](URL): Brief description of what this source verifies.\n"
        )

    advisory_lines = []
    for a in advisories:
        advisory_name = a.get("metadata", {}).get("name", "Unknown Source")
        advisory_lines.append(f"- {a['text']} [Source: {advisory_name}]")
    advisory_context = "\n".join(advisory_lines) or "None"

    context = (
        f"System Verdict: {verdict.upper()} (based on credibility score of {score}/100)\n"
        f"Claim/Context: {claim or '(no text claim provided, checking the image)'}\n\n"
        f"Search query: {search_query}\n\n"
        f"Official Advisories & Reference Documents:\n"
        f"{advisory_context}\n\n"
        f"Cached prior investigations:\n"
        f"{chr(10).join(c['text'][:150] for c in cached) or 'None'}\n\n"
        f"Web search results:\n{source_context}"
        f"{note}"
    )

    # Sample first frame of video if video is provided
    temp_frame_path = None
    image_to_pass = None
    
    if file_path and os.path.exists(file_path) and provider != "ollama":
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
    if language in LANGUAGE_INSTRUCTIONS:
        system_prompt = f"{system_prompt} {LANGUAGE_INSTRUCTIONS[language]}"

    llm = get_provider(provider)
    try:
        explanation = llm.complete(system_prompt, context, image_path=image_to_pass, max_tokens=512)
        
        # Post-processing cleaning to ensure no hallucinated links/sources under empty search results
        if not top_sources and explanation:
            lines = []
            for line in explanation.splitlines():
                if "[" in line and "](" in line:
                    continue
                if line.strip().lower().startswith(("sources:", "source:", "- source", "* source", "sources")):
                    continue
                lines.append(line)
            explanation = "\n".join(lines).strip()
    except Exception as e:
        explanation = (
            f"Found {len(scored_sources)} source(s) with average credibility "
            f"score {score}/100. (LLM explanation unavailable: {e})"
        )
    finally:
        if temp_frame_path and os.path.exists(temp_frame_path):
            try:
                os.remove(temp_frame_path)
            except Exception:
                pass

    # Cache this investigation
    retriever.add(search_query, {
        "score": score,
        "verdict": verdict,
        "top_url": top_sources[0]["url"] if top_sources else None,
        "category": "investigation",
    })

    return {
        "score": score,
        "verdict": verdict,
        "explanation": explanation,
        "sources": top_sources,
        "cached_matches": cached,
        "search_error": search_error,
    }

