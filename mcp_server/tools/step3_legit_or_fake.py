"""
step3_legit_or_fake.py — checks the RAG cache first (has something like
this been investigated before?), then searches the web for anything not
already covered, scores source credibility, and asks the LLM to explain
*why* each source is relevant rather than just listing links.

This is the step where "just detect fake" becomes "teach the user why" —
the explanation is written to be read, not just a score to glance at.
"""

from services.search import google_search
from services.rag import retriever
from services.llm.gemini_client import get_provider
from shared.text_utils import domain_trust, text_similarity, truncate

SYNTHESIS_PROMPT = (
    "You are explaining a fact-check result to someone who may not be "
    "familiar with how to evaluate sources. Given a claim and a list of "
    "search results with credibility scores, write 3-5 sentences that: "
    "(1) state whether the claim looks credible, questionable, or false, "
    "(2) explain which source(s) matter most and specifically why they're "
    "relevant to this claim, (3) note anything that should make the "
    "reader cautious. Be direct. Do not invent facts beyond what's given."
)


def _score_sources(claim: str, results: list[dict]) -> list[dict]:
    scored = []
    for r in results:
        trust = domain_trust(r["url"])
        similarity = text_similarity(claim, r["snippet"])
        scored.append({**r, "domain_trust": round(trust, 2), "text_similarity": round(similarity, 2),
                        "combined": round(trust * 0.6 + similarity * 0.4, 3)})
    return sorted(scored, key=lambda s: s["combined"], reverse=True)


def check_claim(claim: str, provider: str = "ollama") -> dict:
    # 1. Check the local cache first — has something like this been seen before?
    cached = retriever.search(claim, top_k=3)

    # 2. Fresh web search for anything the cache doesn't cover well
    try:
        search_results = google_search.search(claim, max_results=6)
    except Exception as e:
        search_results = []
        search_error = str(e)
    else:
        search_error = None

    scored_sources = _score_sources(claim, search_results)
    score = round(sum(s["combined"] for s in scored_sources) / len(scored_sources) * 100, 1) if scored_sources else 20.0

    if score >= 70:
        verdict = "likely_true"
    elif score >= 45:
        verdict = "inconclusive"
    else:
        verdict = "flagged"

    llm = get_provider(provider)
    context = (
        f"Claim: {claim}\n\n"
        f"Cached prior investigations: {[c['text'][:150] for c in cached] or 'none'}\n\n"
        f"Search results: {[(s['title'], s['url'], s['domain_trust'], s['text_similarity']) for s in scored_sources] or 'none found'}"
    )
    try:
        explanation = llm.complete(SYNTHESIS_PROMPT, context)
    except Exception as e:
        explanation = (
            f"Found {len(scored_sources)} sources with an average credibility "
            f"score of {score}/100. (LLM explanation unavailable: {e})"
        )

    # 3. Cache this investigation for next time
    retriever.add(claim, {"score": score, "verdict": verdict, "top_url": scored_sources[0]["url"] if scored_sources else None})

    return {
        "score": score,
        "verdict": verdict,
        "explanation": explanation,
        "sources": scored_sources,
        "cached_matches": cached,
        "search_error": search_error,
    }
