"""Request-local transcript retrieval with original media timestamps.

No transcript or vector is persisted here: the caller supplies only the segments
for the current authorized analysis request, which keeps retrieval scoped to that
request and avoids cross-project/user indexing risks.
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Protocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TranscriptChunk:
    text: str
    start: float
    end: float
    source_indices: tuple[int, ...]


class Embedder(Protocol):
    def encode(self, texts: list[str]) -> Any: ...


class LocalSentenceEmbedder:
    """Load the configured sentence-transformer only from its local cache."""

    def __init__(self) -> None:
        name = os.getenv("RAG_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        semantic_name = os.getenv("SEMANTIC_MODEL", "all-MiniLM-L6-v2")
        if name == semantic_name:
            # `enrich_semantics` runs earlier in the same analysis pipeline.
            # Reuse its in-process model instead of loading a second copy.
            from .semantic import _load_model

            self.model = _load_model()
            if self.model is not None:
                return
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(name, device="cpu", local_files_only=True)

    def encode(self, texts: list[str]) -> Any:
        return self.model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)


_embedder: Embedder | None = None
_embedder_checked = False
_embedder_lock = threading.Lock()
_vector_cache: OrderedDict[str, tuple[float, ...]] = OrderedDict()
_cache_lock = threading.Lock()
_CACHE_LIMIT = 4096
_CACHE_BYTE_LIMIT = 32 * 1024 * 1024


def _setting(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        return min(max(int(os.getenv(name, default)), minimum), maximum)
    except (TypeError, ValueError, OverflowError):
        return default


def reset_rag_state() -> None:
    """Clear process-local state; intended for tests and controlled reloads."""
    global _embedder, _embedder_checked
    with _embedder_lock, _cache_lock:
        _embedder = None
        _embedder_checked = False
        _vector_cache.clear()


def _get_embedder() -> Embedder | None:
    global _embedder, _embedder_checked
    if _embedder_checked:
        return _embedder
    with _embedder_lock:
        if _embedder_checked:
            return _embedder
        try:
            _embedder = LocalSentenceEmbedder()
        except Exception as exc:
            logger.info("Transcript RAG unavailable (%s)", type(exc).__name__)
            _embedder = None
        _embedder_checked = True
        return _embedder


def rag_enabled() -> bool:
    return os.getenv("RAG_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"}


def _valid_time(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def chunk_transcript(
    segments: list[dict], *, max_words: int = 110, overlap_words: int = 20,
    time_range: tuple[float, float] | None = None, max_gap_seconds: float = 8.0,
) -> list[TranscriptChunk]:
    """Create overlapping word-window chunks and proportionally time long rows."""
    if max_words < 1 or overlap_words < 0 or overlap_words >= max_words:
        raise ValueError("Chunk size must be positive and overlap smaller than chunk size.")
    tokens: list[tuple[str, float, float, int]] = []
    lower, upper = time_range or (None, None)
    for index, segment in enumerate(segments if isinstance(segments, list) else []):
        if not isinstance(segment, dict):
            continue
        start, end = _valid_time(segment.get("start")), _valid_time(segment.get("end"))
        words = str(segment.get("text") or "").split()
        if start is None or end is None or end <= start or not words:
            continue
        start = max(start, lower) if lower is not None else start
        end = min(end, upper) if upper is not None else end
        if end <= start:
            continue
        for word_index, word in enumerate(words):
            word_start = start + (end - start) * word_index / len(words)
            word_end = start + (end - start) * (word_index + 1) / len(words)
            tokens.append((word, word_start, word_end, index))
    if not tokens:
        return []
    tokens.sort(key=lambda token: (token[1], token[2], token[3]))
    step = max_words - overlap_words
    chunks: list[TranscriptChunk] = []
    cursor = 0
    while cursor < len(tokens):
        end_index = min(len(tokens), cursor + max_words)
        for index in range(cursor + 1, end_index):
            if tokens[index][1] - tokens[index - 1][2] > max_gap_seconds:
                end_index = index
                break
        batch = tokens[cursor:end_index]
        if not batch:
            break
        chunks.append(TranscriptChunk(
            text=" ".join(token[0] for token in batch),
            start=min(token[1] for token in batch),
            end=max(token[2] for token in batch),
            source_indices=tuple(dict.fromkeys(token[3] for token in batch)),
        ))
        if end_index >= len(tokens):
            break
        cursor = max(cursor + 1, min(cursor + step, end_index))
    return chunks


def _normalize_vectors(raw: Any, expected: int) -> list[tuple[float, ...]]:
    import numpy as np

    array = np.asarray(raw, dtype=np.float32)
    if array.ndim == 1 and expected == 1:
        array = array.reshape(1, -1)
    if array.ndim != 2 or array.shape[0] != expected or array.shape[1] == 0 or array.shape[1] > 4096:
        raise ValueError("Embedding model returned an invalid vector shape")
    if not np.isfinite(array).all():
        raise ValueError("Embedding model returned non-finite values")
    norms = np.linalg.norm(array, axis=1)
    if np.any(norms <= 0):
        raise ValueError("Embedding model returned a zero vector")
    array = array / norms[:, None]
    return [tuple(float(value) for value in row) for row in array]


def _cache_key(model_key: str, text: str) -> str:
    return model_key + ":" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _embed_texts(embedder: Embedder, texts: list[str], *, batch_size: int | None = None) -> list[tuple[float, ...]]:
    if not texts:
        return []
    model_key = os.getenv("RAG_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    keys = [_cache_key(model_key, text) for text in texts]
    results: list[tuple[float, ...] | None] = [None] * len(texts)
    missing: list[int] = []
    with _cache_lock:
        for index, key in enumerate(keys):
            vector = _vector_cache.get(key)
            if vector is None:
                missing.append(index)
            else:
                _vector_cache.move_to_end(key)
                results[index] = vector
    bounded_batch = batch_size or _setting("RAG_EMBEDDING_BATCH_SIZE", 32, 1, 128)
    for offset in range(0, len(missing), bounded_batch):
        indexes = missing[offset:offset + bounded_batch]
        vectors = _normalize_vectors(embedder.encode([texts[index] for index in indexes]), len(indexes))
        dimensions = {len(vector) for vector in vectors}
        if len(dimensions) != 1:
            raise ValueError("Embedding model returned inconsistent dimensions")
        with _cache_lock:
            for index, vector in zip(indexes, vectors):
                results[index] = vector
                _vector_cache[keys[index]] = vector
                _vector_cache.move_to_end(keys[index])
            while len(_vector_cache) > _CACHE_LIMIT:
                _vector_cache.popitem(last=False)
            while _vector_cache and sum(len(value) * 32 for value in _vector_cache.values()) > _CACHE_BYTE_LIMIT:
                _vector_cache.popitem(last=False)
    if any(vector is None for vector in results):
        raise ValueError("Embedding cache produced incomplete results")
    return [vector for vector in results if vector is not None]


def retrieve_context(
    segments: list[dict], query: str, *, candidate_start: float, candidate_end: float,
    time_range: tuple[float, float] | None = None, embedder: Embedder | None = None,
    limit: int = 3, max_chars: int = 1600, max_words: int | None = None,
    overlap_words: int | None = None,
) -> dict:
    """Retrieve distinct semantically related chunks, favoring nearby context."""
    started = time.monotonic()
    result = {"status": "unavailable", "chunks": [], "durationMs": 0, "candidateCount": 0}
    if not rag_enabled():
        result["status"] = "disabled"
        return result
    chunk_size = max_words if max_words is not None else _setting("RAG_CHUNK_WORDS", 110, 20, 500)
    chunk_overlap = overlap_words if overlap_words is not None else _setting("RAG_CHUNK_OVERLAP_WORDS", 20, 0, 200)
    chunk_overlap = min(max(0, chunk_overlap), max(0, chunk_size - 1))
    try:
        chunks = chunk_transcript(
            segments, max_words=chunk_size, overlap_words=chunk_overlap, time_range=time_range,
        )
    except Exception as exc:
        logger.info("Transcript RAG chunking failed (%s)", type(exc).__name__)
        result["durationMs"] = round((time.monotonic() - started) * 1000, 2)
        return result
    result["candidateCount"] = len(chunks)
    if not chunks or not str(query or "").strip() or limit <= 0 or max_chars <= 0:
        result["status"] = "empty"
        return result
    active_embedder = embedder if embedder is not None else _get_embedder()
    if active_embedder is None:
        result["status"] = "unavailable"
        return result
    try:
        vectors = _embed_texts(active_embedder, [chunk.text for chunk in chunks] + [query])
        if len({len(vector) for vector in vectors}) != 1:
            raise ValueError("Embedding model returned inconsistent dimensions")
        query_vector = vectors[-1]
        qnorm = math.sqrt(sum(value * value for value in query_vector))
        ranked: list[tuple[float, int]] = []
        for index, (chunk, vector) in enumerate(zip(chunks, vectors[:-1])):
            # Prefer context outside the candidate, while retaining overlapping
            # rows if there are no other usable chunks.
            overlap = min(chunk.end, candidate_end) - max(chunk.start, candidate_start)
            if overlap > 0 and chunk.end > chunk.start and overlap / (chunk.end - chunk.start) >= 0.8:
                continue
            semantic = sum(a * b for a, b in zip(vector, query_vector)) / max(qnorm, 1e-12)
            distance = max(0.0, candidate_start - chunk.end, chunk.start - candidate_end)
            temporal = math.exp(-distance / 180.0)
            ranked.append((0.85 * semantic + 0.15 * temporal, index))
        if not ranked:
            ranked = [(sum(a * b for a, b in zip(vector, query_vector)), index)
                      for index, vector in enumerate(vectors[:-1])]
        selected = []
        seen: set[tuple[int, int, str]] = set()
        chars = 0
        for score, index in sorted(ranked, reverse=True):
            chunk = chunks[index]
            identity = (round(chunk.start * 1000), round(chunk.end * 1000), chunk.text.casefold())
            if identity in seen:
                continue
            seen.add(identity)
            text = chunk.text[:max_chars - chars]
            if not text:
                break
            selected.append({"text": text, "start": round(chunk.start, 3), "end": round(chunk.end, 3),
                             "similarity": round(float(score), 4)})
            chars += len(text)
            if len(selected) >= limit or chars >= max_chars:
                break
        result["chunks"] = selected
        result["status"] = "available" if selected else "empty"
    except Exception as exc:
        logger.info("Transcript RAG retrieval failed (%s)", type(exc).__name__)
        result["status"] = "unavailable"
    finally:
        result["durationMs"] = round((time.monotonic() - started) * 1000, 2)
        logger.debug(
            "Transcript RAG status=%s duration_ms=%s candidate_chunks=%s retrieved_chunks=%s",
            result["status"], result["durationMs"], result["candidateCount"], len(result["chunks"]),
        )
    return result


def enrich_candidates_with_context(
    candidates: list[dict], segments: list[dict], *, limit_candidates: int = 20,
    max_chars_per_candidate: int = 600,
) -> tuple[list[dict], dict[int, list[dict]]]:
    """Attach bounded diagnostics and context without changing candidate scores."""
    contexts: dict[int, list[dict]] = {}
    for index, candidate in enumerate(candidates[:max(0, limit_candidates)]):
        start, end = _valid_time(candidate.get("start")), _valid_time(candidate.get("end"))
        if start is None or end is None or end <= start:
            candidate.setdefault("features", {})["transcriptRag"] = {
                "status": "empty", "chunks": [], "durationMs": 0, "candidateCount": 0,
            }
            continue
        query = str(candidate.get("text") or "").strip()
        if not query:
            timed: list[tuple[float, str]] = []
            for segment in segments:
                if not isinstance(segment, dict):
                    continue
                segment_start = _valid_time(segment.get("start"))
                segment_end = _valid_time(segment.get("end"))
                text = str(segment.get("text") or "").strip()
                if segment_start is None or segment_end is None or segment_end <= segment_start or not text:
                    continue
                distance = max(0.0, start - segment_end, segment_start - end)
                if distance <= 30:
                    timed.append((distance, text))
            query = " ".join(text for _, text in sorted(timed)[:4])[:500]
        rag = retrieve_context(
            segments, query, candidate_start=start,
            candidate_end=end, limit=_setting("RAG_RETRIEVAL_LIMIT", 3, 1, 8),
            max_chars=min(max_chars_per_candidate, _setting("RAG_CONTEXT_MAX_CHARS", 600, 100, 2000)),
        )
        candidate.setdefault("features", {})["transcriptRag"] = rag
        if rag["status"] == "available":
            contexts[index] = rag["chunks"]
    for candidate in candidates[max(0, limit_candidates):]:
        candidate.setdefault("features", {})["transcriptRag"] = {
            "status": "skipped_budget", "chunks": [], "durationMs": 0, "candidateCount": 0,
        }
    return candidates, contexts
