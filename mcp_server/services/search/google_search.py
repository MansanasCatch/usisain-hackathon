"""google_search.py — web search for step 3.

Tries Google Custom Search first (requires GOOGLE_API_KEY + GOOGLE_CSE_ID).
Falls back to DuckDuckGo HTML scraping if Google fails or keys are missing.
"""

import os
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, unquote

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.environ.get("GOOGLE_CSE_ID")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def _google_search(query: str, max_results: int) -> list[dict]:
    """Google Custom Search API."""
    resp = requests.get(
        "https://www.googleapis.com/customsearch/v1",
        params={"key": GOOGLE_API_KEY, "cx": GOOGLE_CSE_ID, "q": query, "num": max_results},
        timeout=3,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    return [
        {"title": i.get("title", ""), "url": i.get("link", ""), "snippet": i.get("snippet", "")}
        for i in items
    ]


def _ddg_search(query: str, max_results: int) -> list[dict]:
    """DuckDuckGo Lite search fallback — robust against bot detection."""
    try:
        resp = requests.post(
            "https://lite.duckduckgo.com/lite/",
            data={"q": query},
            headers=_HEADERS,
            timeout=5,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for link in soup.select("a.result-link")[:max_results]:
            title = link.get_text(" ", strip=True)
            url = link.get("href")
            
            snippet = ""
            tr = link.find_parent("tr")
            if tr:
                next_tr = tr.find_next_sibling("tr")
                if next_tr:
                    snippet_td = next_tr.select_one(".result-snippet")
                    if snippet_td:
                        snippet = snippet_td.get_text(" ", strip=True)
                        
            if url:
                if not url.startswith("http"):
                    url = "https://" + url
                results.append({"title": title, "url": url, "snippet": snippet})
        return results
    except Exception as e:
        # Fall back to original DDG search endpoint just in case
        try:
            resp = requests.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers=_HEADERS,
                timeout=3,
            )
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                results = []
                for r in soup.select(".result__body")[:max_results]:
                    title_el = r.select_one(".result__title")
                    url_el = r.select_one(".result__url")
                    snippet_el = r.select_one(".result__snippet")
                    title = title_el.get_text(" ", strip=True) if title_el else ""
                    url = url_el.get_text(" ", strip=True) if url_el else ""
                    snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""
                    if url:
                        if not url.startswith("http"):
                            url = "https://" + url
                        results.append({"title": title, "url": url, "snippet": snippet})
                return results
        except Exception:
            pass
        raise e


def _yahoo_search(query: str, max_results: int) -> list[dict]:
    """Yahoo Search scrape fallback — robust against bot detection."""
    resp = requests.get(
        "https://search.yahoo.com/search",
        params={"p": query},
        headers=_HEADERS,
        timeout=3,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    for item in soup.select(".algo")[:max_results]:
        link_el = item.select_one("a")
        title_el = item.select_one("h3")
        snippet_el = item.select_one(".compText") or item.select_one(".fc-falcon")
        
        title = title_el.get_text(" ", strip=True) if title_el else ""
        url = link_el.get("href") if link_el else ""
        snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""
        
        if url:
            parsed = urlparse(url)
            if "r.search.yahoo.com" in parsed.netloc:
                for part in parsed.path.split("/"):
                    if part.startswith("RU="):
                        url = unquote(part[3:])
                        break
            if not url.startswith("http"):
                url = "https://" + url
            results.append({"title": title, "url": url, "snippet": snippet})
    return results


def _wikipedia_search(query: str, max_results: int) -> list[dict]:
    """Wikipedia search fallback — robust, no API key required."""
    import urllib.parse
    try:
        resp = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "utf8": 1
            },
            headers={"User-Agent": "UsisAIn/1.0 (contact@usisain.org)"},
            timeout=3
        )
        if resp.status_code == 200:
            data = resp.json()
            search_results = data.get("query", {}).get("search", [])
            results = []
            for r in search_results[:max_results]:
                title = r.get("title", "")
                snippet_raw = r.get("snippet", "")
                snippet = re.sub(r'<[^>]*>', '', snippet_raw)
                encoded_title = urllib.parse.quote(title.replace(" ", "_"))
                url = f"https://en.wikipedia.org/wiki/{encoded_title}"
                results.append({
                    "title": title,
                    "url": url,
                    "snippet": snippet
                })
            return results
    except Exception:
        pass
    return []


def search(query: str, max_results: int = 6) -> list[dict]:
    """Search the web. Tries Google CSE first, falls back to Yahoo, DuckDuckGo, then Wikipedia."""
    # Try Google first if credentials are available
    if GOOGLE_API_KEY and GOOGLE_CSE_ID:
        try:
            results = _google_search(query, max_results)
            if results:
                return results
        except Exception:
            pass  # Fall through

    # Fallback 1: Yahoo Search
    try:
        results = _yahoo_search(query, max_results)
        if results:
            return results
    except Exception:
        pass

    # Fallback 2: DuckDuckGo HTML scrape
    try:
        results = _ddg_search(query, max_results)
        if results:
            return results
    except Exception:
        pass

    # Fallback 3: Wikipedia Search API (highly robust, no-key fallback)
    try:
        return _wikipedia_search(query, max_results)
    except Exception as e:
        raise RuntimeError(f"All search backends failed: {e}") from e
