"""Safe interval deduplication for ranked clip candidates."""
from __future__ import annotations

import math
from typing import Any


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _interval(candidate: dict) -> tuple[float, float] | None:
    start = _finite(candidate.get("start"))
    end = _finite(candidate.get("end"))
    if start is None or end is None or start < 0 or end <= start:
        return None
    return start, end


def _iou(a: dict, b: dict) -> float:
    first, second = _interval(a), _interval(b)
    if first is None or second is None:
        return 0.0
    left = max(first[0], second[0])
    right = min(first[1], second[1])
    intersection = max(0.0, right - left)
    union = max(first[1], second[1]) - min(first[0], second[0])
    return intersection / union if union > 0 else 0.0


def deduplicate(candidates: list[dict], threshold: float = 0.55) -> list[dict]:
    """Keep the highest-scoring valid candidate from each overlapping interval group.

    Invalid/non-finite intervals are dropped here as a final defensive boundary;
    the candidate contract remains responsible for normalizing API output.
    """
    if not isinstance(candidates, (list, tuple)):
        return []

    overlap_threshold = _finite(threshold)
    overlap_threshold = min(1.0, max(0.0, overlap_threshold if overlap_threshold is not None else 0.55))
    valid = []
    for candidate in candidates:
        if not isinstance(candidate, dict) or _interval(candidate) is None:
            continue
        item = dict(candidate)
        score = _finite(item.get("score"))
        item["score"] = score if score is not None else 0.0
        valid.append(item)
    kept = []
    for candidate in sorted(valid, key=lambda item: item["score"], reverse=True):
        if all(_iou(candidate, existing) < overlap_threshold for existing in kept):
            kept.append(candidate)
    return kept


def enforce_temporal_diversity(
    candidates: list[dict],
    min_spacing_seconds: float = 15.0,
    max_per_window: int = 2,
    window_size_seconds: float = 120.0,
) -> list[dict]:
    """Re-ranks candidates to prevent over-clustering in narrow time windows.

    Candidates should be sorted descending by score.
    Higher-scoring candidates that are temporally spaced and within window density limits
    are prioritized at the front. Candidates that violate spacing or exceed the window
    density quota are deferred to the tail (preserving their relative score order)
    rather than discarded, ensuring that diversity is promoted while no candidates
    are lost if the caller requests a large set.
    """
    if not isinstance(candidates, (list, tuple)):
        return []
    if not candidates:
        return []

    min_spacing = _finite(min_spacing_seconds)
    min_spacing = max(0.0, min_spacing if min_spacing is not None else 15.0)
    max_density = int(max_per_window) if max_per_window and max_per_window > 0 else 2
    window_size = _finite(window_size_seconds)
    window_size = max(10.0, window_size if window_size is not None else 120.0)

    selected: list[dict] = []
    deferred: list[dict] = []
    window_counts: dict[int, int] = {}

    for cand in candidates:
        if not isinstance(cand, dict):
            continue
        interval = _interval(cand)
        if interval is None:
            deferred.append(cand)
            continue

        start, _ = interval
        window_idx = int(start // window_size)

        too_close = any(
            abs(start - sel_interval[0]) < min_spacing
            for sel in selected
            if (sel_interval := _interval(sel)) is not None
        )

        window_full = window_counts.get(window_idx, 0) >= max_density

        if not too_close and not window_full:
            selected.append(cand)
            window_counts[window_idx] = window_counts.get(window_idx, 0) + 1
        else:
            deferred.append(cand)

    return selected + deferred
