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


def _overlap(a: dict, b: dict) -> tuple[float, float]:
    """Return intersection duration and IoU for two valid intervals."""
    first, second = _interval(a), _interval(b)
    if first is None or second is None:
        return 0.0, 0.0
    intersection = max(0.0, min(first[1], second[1]) - max(first[0], second[0]))
    union = max(first[1], second[1]) - min(first[0], second[0])
    return intersection, intersection / union if union > 0 else 0.0


def _same_moment(a: dict, b: dict, threshold: float) -> bool:
    """Detect duplicates by IoU or by coverage of the shorter candidate.

    IoU alone misses duplicates when one detector proposes a broad setup/payoff
    window and another proposes a tighter clip fully inside it. Coverage of the
    shorter interval catches that case without merging candidates that merely
    touch or have a small overlap.
    """
    intersection, iou = _overlap(a, b)
    first, second = _interval(a), _interval(b)
    if first is None or second is None or intersection <= 0:
        return False
    shorter_duration = min(first[1] - first[0], second[1] - second[0])
    coverage = intersection / shorter_duration if shorter_duration > 0 else 0.0
    return max(iou, coverage) >= threshold


def deduplicate(candidates: list[dict], threshold: float = 0.55) -> list[dict]:
    """Keep the highest-scoring valid candidate from each overlapping moment group.

    The threshold is compared with both interval IoU and the fraction of the
    shorter interval covered by the overlap. Invalid/non-finite intervals are
    dropped here as a final defensive boundary; the candidate contract remains
    responsible for normalizing API output.
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
        if all(not _same_moment(candidate, existing, overlap_threshold) for existing in kept):
            kept.append(candidate)
    return kept
