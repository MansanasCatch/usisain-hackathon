"""embeddings.py — deliberately lightweight: TF-IDF via scikit-learn
instead of a transformer embedding model. This avoids pulling in torch/
sentence-transformers (large downloads, slow on CPU-only Windows
machines) for what is, for this use case, a "have we seen text like this
before" lookup rather than deep semantic search. Swap this out for real
embeddings later if TF-IDF's keyword-level matching isn't precise enough
for your content."""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def rank_by_similarity(query: str, documents: list[str]) -> list[float]:
    """Returns a similarity score (0-1) for `query` against each of
    `documents`, in the same order as `documents`."""
    if not documents:
        return []
    vectorizer = TfidfVectorizer(stop_words="english")
    matrix = vectorizer.fit_transform([query] + documents)
    scores = cosine_similarity(matrix[0:1], matrix[1:]).flatten()
    return scores.tolist()
