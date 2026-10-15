"""Shared validation contract for AI-generated clip candidates.

This is genre-neutral: every genre must produce candidates with safe timestamps,
finite scores, and enough evidence to inspect. It validates output; it does not
claim that a candidate is interesting or genre-correct.
"""
from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any


def _finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def validate_candidates(
    candidates: Iterable[dict[str, Any]],
    media_duration: float | None = None,
) -> list[dict[str, Any]]:
    """Normalize candidate shape and discard invalid/out-of-source intervals.

    If a candidate ends slightly or substantially beyond the source duration,
    its end is clipped to the actual media boundary. Candidates starting at or
    after the source end are rejected. Scores are clamped to [0, 100].
    """
    duration_limit = _finite_number(media_duration)
    if duration_limit is not None and duration_limit <= 0:
        duration_limit = None

    valid: list[dict[str, Any]] = []
    for raw in candidates:
        if not isinstance(raw, dict):
            continue

        start = _finite_number(raw.get("start"))
        end = _finite_number(raw.get("end"))
        score = _finite_number(raw.get("score"))
        if start is None or end is None or score is None:
            continue

        start = max(0.0, start)
        if duration_limit is not None:
            if start >= duration_limit:
                continue
            end = min(end, duration_limit)
        if end <= start:
            continue

        text = str(raw.get("text") or "").strip()
        features = raw.get("features")
        features = features if isinstance(features, dict) else {}
        # Permit visual-only candidates in future genre pipelines, but only
        # when the detector provides inspectable feature evidence.
        if not text and not features:
            continue

        candidate = dict(raw)
        candidate["start"] = round(start, 3)
        candidate["end"] = round(end, 3)
        candidate["duration"] = round(end - start, 3)
        candidate["score"] = round(max(0.0, min(100.0, score)), 2)
        candidate["text"] = text
        candidate["features"] = features
        candidate["rationale"] = str(candidate.get("rationale") or "").strip()
        valid.append(candidate)

    return valid
