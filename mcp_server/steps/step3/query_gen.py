import os
import re
from mcp_server.prompts.step3_prompts import QUERY_GEN_PROMPT
from mcp_server.services.llm import get_provider

STOPWORDS = {
    "the", "is", "a", "and", "or", "in", "of", "to", "on", "at", "by", "for",
    "with", "from", "this", "that", "it", "its", "are", "was", "were", "be",
    "been", "have", "has", "had", "latest", "new", "about", "may", "can",
    "will", "would", "should", "ang", "mga", "ng", "sa", "na", "ni", "at",
    "ay", "si", "para", "kay", "ng mga", "nang", "yung", "iyong", "itong",
    "bilang", "habang", "nasa", "ito", "siya", "nila", "kami", "tayo",
    "may", "mayroon", "maging", "dahil"
}


def extract_fast_query(claim: str) -> str:
    if not claim:
        return ""

    urls = re.findall(r"https?://(?:www\.)?([a-zA-Z0-9.-]+)(/[^\s]*)?", claim)
    if urls:
        domain, path = urls[0]
        domain_parts = [
            p
            for p in domain.split(".")
            if p not in ("com", "org", "net", "gov", "edu", "ph", "www")
        ]
        keywords = list(domain_parts)
        if path:
            path_words = re.findall(r"[a-zA-Z0-9]+", path)
            keywords.extend([
                w
                for w in path_words
                if w.lower()
                not in ("html", "php", "htm", "asp", "jsp", "index")
            ])
        url_query = " ".join(keywords[:5])
        if url_query:
            cap_words = re.findall(r"\b[A-Z][a-z]+\b", claim)
            cap_words = [w for w in cap_words if w.lower() not in url_query.lower()]
            final_query = f"{url_query} " + " ".join(cap_words[:2])
            return final_query.strip()

    words = re.findall(r"\b[a-zA-Z0-9-]+\b", claim)
    if not words:
        return ""

    first_word = words[0].lower()
    scored_words = []
    seen = set()
    for idx, w in enumerate(words):
        w_lower = w.lower()
        if w_lower in STOPWORDS or len(w) < 2 or w_lower in seen:
            continue
        seen.add(w_lower)
        score = 0
        if w[0].isupper() and w_lower != first_word:
            score += 10
        score += min(len(w) * 0.1, 1.0)
        score += max(0, (len(words) - idx) / len(words) * 0.5)
        scored_words.append((w, score, idx))

    scored_words.sort(key=lambda item: item[1], reverse=True)
    top_items = scored_words[:5]
    top_items.sort(key=lambda item: item[2])
    result_query = " ".join(item[0] for item in top_items)
    return result_query or " ".join(words[:5])


async def generate_search_query(
    claim: str,
    file_path: str | None = None,
    content_type: str = "text",
    provider: str = "ollama",
    step1_result: dict | None = None,
    step2_result: dict | None = None,
) -> str:
    fast_gen = os.environ.get("STEP3_FAST_QUERY_GEN", "True").lower() in (
        "1",
        "true",
        "yes",
    )
    if fast_gen and claim:
        fast_query = extract_fast_query(claim)
        if fast_query:
            return fast_query

    step1_text = ""
    if step1_result:
        step1_text = (
            step1_result.get("insight") or step1_result.get("explanation") or ""
        )
    step2_text = ""
    if step2_result and step2_result.get("applicable") is not False:
        step2_text = step2_result.get("explanation") or ""

    desc_text = f"{step1_text} {step2_text}".strip()
    if fast_gen and not claim and desc_text:
        fast_query = extract_fast_query(desc_text)
        if fast_query:
            return fast_query

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
        query = await llm.complete(
            QUERY_GEN_PROMPT, context_for_query, max_tokens=30
        )
        query = " ".join(query.split()).strip().replace('"', "").replace("'", "")
        if query:
            return query
    except Exception:
        pass

    if claim:
        return claim
    if desc_text:
        words = desc_text.split()
        return " ".join(words[:6])
    return ""
