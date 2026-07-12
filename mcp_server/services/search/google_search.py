"""google_search.py — source lookup for step 3. Get credentials at:
  API key:            https://console.cloud.google.com/apis/credentials
  Search engine (cx): https://programmablesearchengine.google.com/
  (set the search engine to search the entire web, not a specific site)
"""

import os
import requests

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.environ.get("GOOGLE_CSE_ID")


def search(query: str, max_results: int = 6) -> list[dict]:
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        raise RuntimeError(
            "GOOGLE_API_KEY / GOOGLE_CSE_ID not set — see README for where to get them."
        )
    resp = requests.get(
        "https://www.googleapis.com/customsearch/v1",
        params={"key": GOOGLE_API_KEY, "cx": GOOGLE_CSE_ID, "q": query, "num": max_results},
        timeout=15,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    return [
        {"title": i.get("title", ""), "url": i.get("link", ""), "snippet": i.get("snippet", "")}
        for i in items
    ]
