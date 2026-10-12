import re
from mcp_server.constants import SOURCE_SIMILARITY_WEIGHT, SOURCE_TRUST_WEIGHT
from mcp_server.shared.text_utils import domain_trust, text_similarity


STOPWORDS = {
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

GENERIC_TERMS = {
    "senator", "judge", "senator-judge", "mayor", "president", "vice", "governor",
    "congressman", "representative", "minister", "analyst", "forensic", "financial",
    "official", "spokesperson", "lawyer", "attorney", "prosecutor", "prosecution",
    "defense", "witness", "court", "hearing", "trial", "case", "investigation",
    "scandal", "corruption", "fraud", "statement", "announcement", "report", "article",
    "december", "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "year", "years", "network", "channel",
    "facebook", "youtube", "twitter", "online", "portal", "profile", "story", "watch",
    "alegasyon", "patotoo", "pahayag", "balita", "tanong", "testigo"
}


def is_source_relevant(source: dict, claim: str, query: str = "") -> bool:
    """Verify that a search result is genuinely about the subject of the claim/query.

    Strictly filters out unrelated topics, foreign Wikipedia articles, and sources
    that only coincidentally share generic job titles or common nouns.
    """
    url = (source.get("url") or "").strip()
    title = (source.get("title") or "").strip().lower()
    snippet = (source.get("snippet") or "").strip().lower()
    content = f"{title} {snippet} {url.lower()}"

    combined_input = f"{claim} {query}".lower()

    # 1. Wikipedia / Encyclopedia topic check:
    # In Wikipedia URLs (e.g. wikipedia.org/wiki/Jeffrey_Epstein), the slug is the specific subject.
    wiki_match = re.search(r"wikipedia\.org/wiki/([^/?#]+)", url, re.IGNORECASE)
    if wiki_match:
        slug = wiki_match.group(1).replace("_", " ").lower()
        slug_words = [w for w in re.findall(r"\b[a-z0-9]{3,}\b", slug) if w not in STOPWORDS]
        # At least one meaningful word from the Wikipedia title/slug MUST appear in the claim or query
        if slug_words and not any(sw in combined_input for sw in slug_words):
            return False

    # 2. Extract distinctive named entities (proper nouns / capitalized words)
    raw_tokens = re.findall(r"\b[a-zA-Z0-9_\u00C0-\u024F]{3,}\b", f"{claim} {query}")
    named_entities = {
        w.lower()
        for w in raw_tokens
        if (w[0].isupper() or w.isupper())
        and w.lower() not in STOPWORDS
        and w.lower() not in GENERIC_TERMS
    }

    if named_entities:
        # At least ONE of the core named entities MUST be present in the source title, snippet, or URL
        has_entity_match = any(ne in content for ne in named_entities)
        if not has_entity_match:
            return False

    # 3. Informative content keywords (ignoring stopwords and generic titles/months)
    words = re.findall(r"\b[a-zA-Z0-9_\u00C0-\u024F]{3,}\b", combined_input)
    informative_keywords = [
        w for w in words
        if w not in STOPWORDS and w not in GENERIC_TERMS and len(w) > 3
    ]
    if informative_keywords:
        unique_info = set(informative_keywords)
        match_count = sum(1 for kw in unique_info if kw in content)
        required = 1 if len(unique_info) <= 2 else 2
        if match_count < required:
            return False

    return True


def score_sources(claim: str, results: list[dict], query: str = "") -> list[dict]:
    scored = []
    for r in results:
        # Strictly reject unrelated results that don't match the subject entities
        if not is_source_relevant(r, claim, query):
            continue

        trust = domain_trust(r.get("url", ""))
        similarity = text_similarity(claim, r.get("snippet", ""))

        # Low similarity sources should not be accepted as fact-checking evidence
        if similarity < 0.25:
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
