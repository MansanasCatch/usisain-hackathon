import re
from mcp_server.constants import SOURCE_SIMILARITY_WEIGHT, SOURCE_TRUST_WEIGHT
from mcp_server.shared.text_utils import domain_trust, text_similarity


def is_source_relevant(source: dict, claim: str, query: str = "") -> bool:
    """Verify that a search result contains key entity/subject keywords from the claim or query."""
    title = (source.get("title") or "").lower()
    snippet = (source.get("snippet") or "").lower()
    url = (source.get("url") or "").lower()
    content = f"{title} {snippet} {url}"

    combined_input = f"{claim} {query}".lower()
    words = re.findall(r"\b[a-zA-Z0-9_\u00C0-\u024F]{3,}\b", combined_input)
    stopwords = {
        "the", "and", "that", "this", "with", "from", "for", "are", "was", "were", "been",
        "have", "has", "had", "what", "when", "where", "which", "who", "whom", "will", "would",
        "can", "could", "should", "about", "into", "through", "during", "before", "after",
        "above", "below", "between", "under", "again", "further", "then", "once", "here",
        "there", "all", "any", "both", "each", "few", "more", "most", "other", "some", "such",
        "only", "own", "same", "than", "too", "very", "just", "now", "tama", "mali", "noon",
        "noong", "nagkita", "kayo", "sila", "siya", "kami", "tayo", "nila", "namin", "ninyo",
        "kanila", "kanya", "aking", "iyong", "lahat", "isang", "mga", "para", "dahil", "kung",
        "pero", "ngunit", "subalit", "dapat", "hindi", "wala", "meron", "mayroon", "post",
        "image", "video", "photo", "news", "update", "updates", "today", "yesterday", "site",
        "page", "read", "view", "more", "comment", "comments", "share"
    }
    keywords = [w for w in words if w not in stopwords and len(w) > 3]
    if not keywords:
        keywords = [w for w in words if len(w) > 3]
    if not keywords:
        return True

    unique_keywords = set(keywords)
    match_count = sum(1 for kw in unique_keywords if kw in content)
    required = 1 if len(unique_keywords) <= 2 else 2
    return match_count >= required


def score_sources(claim: str, results: list[dict], query: str = "") -> list[dict]:
    scored = []
    for r in results:
        # Strictly reject unrelated results that don't match the subject entities
        if not is_source_relevant(r, claim, query):
            continue

        trust = domain_trust(r.get("url", ""))
        similarity = text_similarity(claim, r.get("snippet", ""))

        # Low similarity sources should not be accepted as fact-checking evidence
        if similarity < 0.20:
            continue

        combined = round(trust * SOURCE_TRUST_WEIGHT + similarity * SOURCE_SIMILARITY_WEIGHT, 3)
        scored.append(
            {
                **r,
                "domain_trust": round(trust, 2),
                "text_similarity": round(similarity, 2),
                "combined": combined,
            }
        )
    return sorted(scored, key=lambda s: s["combined"], reverse=True)


def deduplicate_sources(scored_sources: list[dict]) -> list[dict]:
    seen_urls = set()
    seen_titles = set()
    deduped = []
    for s in scored_sources:
        url = s.get("url", "").strip()
        title = s.get("title", "").strip().lower()
        if not url:
            continue
        norm_url = url.lower().split("?")[0].rstrip("/")
        if norm_url.startswith("http://"):
            norm_url = "https://" + norm_url[7:]
        if norm_url not in seen_urls and title not in seen_titles:
            seen_urls.add(norm_url)
            seen_titles.add(title)
            deduped.append(s)
    return deduped
