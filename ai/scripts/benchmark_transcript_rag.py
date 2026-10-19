"""Repeatable, labeled-data-free engineering benchmark for transcript RAG.

Run from the repository root with:
  python ai/scripts/benchmark_transcript_rag.py --test-embeddings

Test embeddings are deterministic and are never used by the service. Omitting
the flag exercises the cached local sentence-transformer and safely reports an
unavailable result if it is not installed.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ai.services.transcript_rag import retrieve_context  # noqa: E402


class _TestOnlyEmbedder:
    def encode(self, texts: list[str]) -> np.ndarray:
        return np.asarray([
            [1.0, 0.0] if any(word in text.lower() for word in ("launch", "worked", "finally"))
            else [0.0, 1.0]
            for text in texts
        ], dtype=np.float32)


def run(test_embeddings: bool = False) -> dict:
    segments = [
        {"start": 100, "end": 108, "text": "The launch failed twice, and nobody knew why."},
        {"start": 110, "end": 118, "text": "We changed the last setting before trying again."},
        {"start": 120, "end": 127, "text": "It finally worked; the whole room cheered."},
        {"start": 300, "end": 308, "text": "Tomorrow's weather should be mild and sunny."},
    ]
    candidates = [
        {"id": "payoff", "start": 120, "end": 127, "score": 82, "text": "It finally worked"},
        {"id": "weather", "start": 300, "end": 308, "score": 76, "text": "Mild and sunny"},
    ]
    embedder = _TestOnlyEmbedder() if test_embeddings else None
    baseline_order = [item["id"] for item in sorted(candidates, key=lambda item: item["score"], reverse=True)]
    start_time = time.monotonic()
    retrieved_count = 0
    context_chars = 0
    statuses = []
    for item in candidates:
        context = retrieve_context(
            segments, item["text"], candidate_start=item["start"], candidate_end=item["end"],
            embedder=embedder, limit=3, max_chars=600,
        )
        statuses.append(context["status"])
        retrieved_count += len(context["chunks"])
        context_chars += sum(len(row["text"]) for row in context["chunks"])
    elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
    # RAG contributes context to the already-configured scorer. This harness
    # runs no LLM, so deterministic scores and their ranking must be identical.
    rag_order = baseline_order[:]
    return {
        "dataset": "synthetic-unlabeled-v1",
        "embeddingMode": "test-only-deterministic" if test_embeddings else "cached-local-model",
        "baselineCandidateCount": len(candidates),
        "ragCandidateCount": len(candidates),
        "retrievalStatuses": statuses,
        "retrievedChunks": retrieved_count,
        "contextCharacters": context_chars,
        "retrievalWallTimeMs": elapsed_ms,
        "extraLlmCalls": 0,
        "baselineOrder": baseline_order,
        "ragOrderWithoutLlm": rag_order,
        "rankingChangesWithoutLlm": sum(a != b for a, b in zip(baseline_order, rag_order)),
        "humanRelevanceMeasured": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-embeddings", action="store_true", help="Use deterministic non-production vectors")
    args = parser.parse_args()
    print(json.dumps(run(args.test_embeddings), indent=2))
