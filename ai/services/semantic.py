import os
import re
from functools import lru_cache

_MODEL = None

def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())

@lru_cache(maxsize=1)
def _load_model():
    global _MODEL
    try:
        from sentence_transformers import SentenceTransformer
        name = os.getenv("SEMANTIC_MODEL", "all-MiniLM-L6-v2")
        _MODEL = SentenceTransformer(name)
        return _MODEL
    except Exception:
        return None

def _lexical_similarity(a: str, b: str) -> float:
    aa, bb = set(_tokens(a)), set(_tokens(b))
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / max(1, len(aa | bb))

def semantic_scores(texts: list[str], query: str | None = None) -> list[float]:
    if not texts:
        return []
    model = _load_model()
    if model is None:
        if not query:
            return [0.0] * len(texts)
        return [round(_lexical_similarity(t, query) * 100, 2) for t in texts]
    try:
        embeddings = model.encode(texts, normalize_embeddings=True)
        if query:
            q = model.encode([query], normalize_embeddings=True)[0]
            return [round(float(emb @ q) * 100, 2) for emb in embeddings]
        return [0.0] * len(texts)
    except Exception:
        return [0.0] * len(texts)

def enrich_semantics(candidates: list[dict], instruction: str | None = None) -> list[dict]:
    if not candidates:
        return candidates
    texts = [str(c.get("text", "")) for c in candidates]
    scores = semantic_scores(texts, instruction)
    for c, value in zip(candidates, scores):
        c.setdefault("features", {})["semanticInstructionScore"] = value
        if instruction and value:
            c["score"] = round(min(100, float(c.get("score", 0)) * 0.82 + value * 0.18), 2)
    return candidates
