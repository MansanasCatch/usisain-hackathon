"""
retriever.py — the local knowledge cache step 3 checks before hitting
Google Search. Every fact-check result gets added here, so a claim
that's already been investigated once (a recurring GCash scam text, for
example) gets answered from cache instantly on repeat sightings, with a
fresh search only for genuinely new claims.

Storage: a single JSON file under data/vector_index/. This is a POC-scale
store — fine for thousands of entries. If you outgrow it, swap this
module for a real vector DB (Chroma, Qdrant) without touching callers,
since they only see add() and search().
"""

import json
import uuid
from pathlib import Path

from .embeddings import rank_by_similarity

STORE_PATH = Path(__file__).resolve().parents[3] / "data" / "vector_index" / "store.json"
STORE_PATH.parent.mkdir(parents=True, exist_ok=True)


def _load() -> list[dict]:
    if not STORE_PATH.exists():
        return []
    return json.loads(STORE_PATH.read_text(encoding="utf-8"))


def _save(entries: list[dict]) -> None:
    STORE_PATH.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def add(text: str, metadata: dict) -> str:
    entries = _load()
    entry_id = uuid.uuid4().hex
    entries.append({"id": entry_id, "text": text, "metadata": metadata})
    _save(entries)
    return entry_id


def search(query: str, top_k: int = 3, min_score: float = 0.35) -> list[dict]:
    entries = _load()
    if not entries:
        return []
    scores = rank_by_similarity(query, [e["text"] for e in entries])
    ranked = sorted(zip(entries, scores), key=lambda pair: pair[1], reverse=True)
    return [
        {**entry, "similarity": round(score, 3)}
        for entry, score in ranked[:top_k] if score >= min_score
    ]
