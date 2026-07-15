import os
import requests
import numpy as np

def get_embedding(text: str) -> list[float]:
    """Generates a 768-dimensional float vector for `text` using local Ollama nomic-embed-text."""
    if not text or not text.strip():
        return [0.0] * 768
    
    clean_text = " ".join(text.split())
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").strip()
    try:
        resp = requests.post(
            f"{host}/api/embeddings",
            json={"model": "nomic-embed-text", "prompt": clean_text},
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json()["embedding"]
    except Exception as e:
        print(f"Error fetching Ollama embedding: {e}")
        
    return [0.0] * 768

def rank_by_similarity(query_vector: list[float], document_vectors: list[list[float]]) -> list[float]:
    """Returns cosine similarity scores (0-1) between the query vector and document vectors using numpy."""
    if not document_vectors:
        return []
        
    q_arr = np.array(query_vector, dtype=np.float32)
    d_arr = np.array(document_vectors, dtype=np.float32)
    
    # Cosine Similarity = (A . B) / (||A|| * ||B||)
    dot_products = np.dot(d_arr, q_arr)
    
    q_norm = np.linalg.norm(q_arr)
    d_norms = np.linalg.norm(d_arr, axis=1)
    
    denominator = q_norm * d_norms
    denominator[denominator == 0] = 1e-8
    
    scores = dot_products / denominator
    scores = np.clip(scores, 0.0, 1.0)
    return scores.tolist()
