"""text_utils.py — small text helpers shared across tools. Kept dependency-
free (stdlib only) so it never blocks step 2 or step 1 from running."""

import difflib

# Domains that get a trust boost during source scoring. Extend this list
# freely — it's the single biggest lever for tuning step 3's accuracy on
# Philippine-specific content.
TRUSTED_DOMAINS = {

    # ==========================================
    # PHILIPPINE GOVERNMENT (Highest Trust)
    # ==========================================
    "gov.ph": 1.0,
    "dti.gov.ph": 1.0,
    "dict.gov.ph": 1.0,
    "doh.gov.ph": 1.0,
    "dilg.gov.ph": 1.0,
    "deped.gov.ph": 1.0,
    "ched.gov.ph": 1.0,
    "comelec.gov.ph": 1.0,
    "senate.gov.ph": 1.0,
    "house.gov.ph": 1.0,
    "officialgazette.gov.ph": 1.0,
    "pco.gov.ph": 1.0,
    "psa.gov.ph": 1.0,
    "pagasa.dost.gov.ph": 1.0,
    "dost.gov.ph": 1.0,
    "nbi.gov.ph": 1.0,
    "pnp.gov.ph": 1.0,
    "bsp.gov.ph": 1.0,
    "sec.gov.ph": 1.0,
    "bir.gov.ph": 1.0,
    "philgeps.gov.ph": 1.0,


    # ==========================================
    # PHILIPPINE CYBERSECURITY / SCAM REPORTING
    # ==========================================
    "cybercrime.doj.gov.ph": 1.0,
    "ncsc.gov.ph": 1.0,
    "privacy.gov.ph": 1.0,
    "cert.ph": 0.95,


    # ==========================================
    # PHILIPPINE UNIVERSITIES / RESEARCH
    # ==========================================
    "edu.ph": 0.9,
    "up.edu.ph": 0.95,
    "dlsu.edu.ph": 0.9,
    "ateneo.edu": 0.9,
    "ust.edu.ph": 0.9,
    "addu.edu.ph": 0.85,
    "sws.org.ph": 0.95,

    # ==========================================
    # PHILIPPINE MAINSTREAM NEWS
    # ==========================================
    "rappler.com": 0.85,
    "abs-cbn.com": 0.85,
    "news.abs-cbn.com": 0.85,
    "gmanetwork.com": 0.85,
    "gmanews.tv": 0.85,
    "philstar.com": 0.8,
    "inquirer.net": 0.8,
    "manilatimes.net": 0.75,
    "manilabulletin.ph": 0.75,
    "pna.gov.ph": 0.95,
    "businessmirror.com.ph": 0.75,
    "sunstar.com.ph": 0.7,


    # ==========================================
    # PH FACT CHECKING
    # ==========================================
    "factcheck.afp.com": 0.95,
    "verafiles.org": 0.95,
    "rappler.com/newsbreak/fact-check": 0.9,
    "tsek.ph": 0.95,


    # ==========================================
    # INTERNATIONAL NEWS ORGANIZATIONS
    # ==========================================
    "reuters.com": 0.95,
    "apnews.com": 0.95,
    "bbc.com": 0.95,
    "bbc.co.uk": 0.95,
    "cnn.com": 0.85,
    "nytimes.com": 0.85,
    "washingtonpost.com": 0.85,
    "theguardian.com": 0.85,
    "aljazeera.com": 0.8,
    "npr.org": 0.85,


    # ==========================================
    # INTERNATIONAL FACT CHECKING
    # ==========================================
    "factcheck.org": 0.95,
    "politifact.com": 0.9,
    "snopes.com": 0.9,
    "fullfact.org": 0.95,
    "leadstories.com": 0.85,
    "afp.com": 0.9,


    # ==========================================
    # INTERNATIONAL ORGANIZATIONS
    # ==========================================
    "un.org": 1.0,
    "who.int": 1.0,
    "worldbank.org": 0.95,
    "imf.org": 0.95,
    "oecd.org": 0.95,
    "wto.org": 0.95,
    "unesco.org": 0.95,


    # ==========================================
    # SCIENCE / MEDICAL
    # ==========================================
    "nih.gov": 1.0,
    "cdc.gov": 1.0,
    "nature.com": 0.95,
    "sciencedirect.com": 0.9,
    "pubmed.ncbi.nlm.nih.gov": 1.0,


    # ==========================================
    # TECHNOLOGY / SECURITY
    # ==========================================
    "microsoft.com": 0.95,
    "apple.com": 0.95,
    "google.com": 0.95,
    "cloudflare.com": 0.9,
    "krebsonsecurity.com": 0.9,
    "bleepingcomputer.com": 0.85,


    # ==========================================
    # FINANCIAL TRUST SOURCES
    # ==========================================
    "bsp.gov.ph": 1.0,
    "sec.gov.ph": 1.0,
    "consumerfinance.gov": 0.95,
    "fdic.gov": 0.95,

}
DEFAULT_TRUST = 0.4  # unknown domains start here, not zero


def domain_trust(url: str) -> float:
    for domain, weight in TRUSTED_DOMAINS.items():
        if domain in url:
            return weight
    return DEFAULT_TRUST


def text_similarity(a: str, b: str) -> float:
    import re
    # Clean and tokenize words (ignoring short words)
    a_clean = re.sub(r'[^\w\s]', ' ', a.lower())
    b_clean = re.sub(r'[^\w\s]', ' ', b.lower())
    
    a_words = set(w for w in a_clean.split() if len(w) > 2)
    b_words = set(w for w in b_clean.split() if len(w) > 2)
    
    if not a_words or not b_words:
        return 0.0
        
    # Keyword overlap ratio: size of intersection divided by min size
    overlap = len(a_words.intersection(b_words)) / min(len(a_words), len(b_words))
    
    # Exact sequence match ratio
    seq_ratio = difflib.SequenceMatcher(None, a_clean, b_clean).ratio()
    
    # Return the maximum of keyword overlap or sequence match
    return max(overlap, seq_ratio)


def truncate(text: str, max_chars: int = 400) -> str:
    text = text.strip()
    return text if len(text) <= max_chars else text[:max_chars].rsplit(" ", 1)[0] + "..."
