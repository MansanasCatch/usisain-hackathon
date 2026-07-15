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

from .embeddings import get_embedding, rank_by_similarity

STORE_PATH = Path(__file__).resolve().parents[3] / "data" / "vector_index" / "store.json"
STORE_PATH.parent.mkdir(parents=True, exist_ok=True)


def _load() -> list[dict]:
    if not STORE_PATH.exists():
        return []
    try:
        return json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(entries: list[dict]) -> None:
    STORE_PATH.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def add(text: str, metadata: dict) -> str:
    entries = _load()
    entry_id = uuid.uuid4().hex
    # Fetch semantic embedding for the new document entry
    vector = get_embedding(text)
    entries.append({
        "id": entry_id,
        "text": text,
        "embedding": vector,
        "metadata": metadata
    })
    _save(entries)
    return entry_id


def search(query: str, top_k: int = 3, min_score: float = 0.35, category: str | None = None) -> list[dict]:
    entries = _load()
    if not entries:
        return []
    
    # 1. Backward-compatibility auto-migration for legacy entries that lack vectors
    dirty = False
    for entry in entries:
        if "embedding" not in entry or not isinstance(entry["embedding"], list) or len(entry["embedding"]) != 768:
            entry["embedding"] = get_embedding(entry["text"])
            dirty = True
        if "metadata" not in entry or entry["metadata"] is None:
            entry["metadata"] = {}
            dirty = True
        if "category" not in entry["metadata"]:
            entry["metadata"]["category"] = "investigation"
            dirty = True
    if dirty:
        _save(entries)
        
    # 2. Filter by category if specified
    filtered_entries = entries
    if category is not None:
        filtered_entries = [e for e in entries if e.get("metadata", {}).get("category") == category]
        
    if not filtered_entries:
        return []
        
    # 3. Get embedding vector for the search query
    query_vector = get_embedding(query)
    
    # 4. Calculate similarities using numpy-accelerated cosine similarity
    doc_vectors = [e["embedding"] for e in filtered_entries]
    scores = rank_by_similarity(query_vector, doc_vectors)
    
    # 5. Rank and filter by minimum similarity score
    ranked = []
    for entry, score in zip(filtered_entries, scores):
        # Exclude embedding vector from output payload for cleaner display
        clean_entry = {k: v for k, v in entry.items() if k != "embedding"}
        ranked.append((clean_entry, score))
        
    ranked.sort(key=lambda pair: pair[1], reverse=True)
    
    return [
        {**entry, "similarity": round(score, 3)}
        for entry, score in ranked[:top_k] if score >= min_score
    ]
