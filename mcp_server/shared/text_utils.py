"""text_utils.py — small text helpers shared across tools. Kept dependency-
free (stdlib only) so it never blocks step 2 or step 1 from running."""

import difflib

# Domains that get a trust boost during source scoring. Extend this list
# freely — it's the single biggest lever for tuning step 3's accuracy on
# Philippine-specific content.
TRUSTED_DOMAINS = {
    "gov.ph": 1.0, "gov": 0.9, "edu": 0.85, "edu.ph": 0.85,
    "reuters.com": 0.95, "apnews.com": 0.95, "rappler.com": 0.85,
    "abs-cbn.com": 0.8, "gmanetwork.com": 0.8, "philstar.com": 0.75,
    "inquirer.net": 0.75, "factcheck.org": 0.95, "afp.com": 0.9,
}
DEFAULT_TRUST = 0.4  # unknown domains start here, not zero


def domain_trust(url: str) -> float:
    for domain, weight in TRUSTED_DOMAINS.items():
        if domain in url:
            return weight
    return DEFAULT_TRUST


def text_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def truncate(text: str, max_chars: int = 400) -> str:
    text = text.strip()
    return text if len(text) <= max_chars else text[:max_chars].rsplit(" ", 1)[0] + "..."
