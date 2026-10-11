from mcp_server.constants import SOURCE_SIMILARITY_WEIGHT, SOURCE_TRUST_WEIGHT
from mcp_server.shared.text_utils import domain_trust, text_similarity


def score_sources(claim: str, results: list[dict]) -> list[dict]:
    scored = []
    for r in results:
        trust = domain_trust(r["url"])
        similarity = text_similarity(claim, r["snippet"])
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
