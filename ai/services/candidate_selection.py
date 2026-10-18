"""Score-aware temporal diversification for final AI clip recommendations."""
from __future__ import annotations

import math
from typing import Any


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def select_temporally_diverse(
    candidates: list[dict],
    limit: int = 50,
    min_center_distance: float = 20.0,
) -> list[dict]:
    """Prefer high-scoring clips spread across the timeline, with safe backfill.

    First pass picks the highest-scoring candidate only when its midpoint is at
    least min_center_distance seconds from already-selected midpoints.
    A second pass fills unused slots with remaining candidates by score, so
    diversity never reduces the result count when enough valid candidates exist.
    Input order is not mutated and malformed intervals are ignored.
    """
    if not isinstance(candidates, (list, tuple)):
        return []
    try:
        max_items = int(limit)
    except (TypeError, ValueError, OverflowError):
        max_items = 50
    max_items = max(0, min(200, max_items))
    if max_items == 0:
        return []

    distance = _finite(min_center_distance)
    distance = max(0.0, distance if distance is not None else 20.0)

    valid: list[tuple[int, dict, float, float]] = []
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            continue
        start = _finite(candidate.get("start"))
        end = _finite(candidate.get("end"))
        score = _finite(candidate.get("score"))
        if start is None or end is None or score is None or start < 0 or end <= start:
            continue
        valid.append((index, candidate, (start + end) / 2.0, score))

    ranked = sorted(valid, key=lambda item: (-item[3], item[0]))
    selected: list[tuple[int, dict, float, float]] = []
    selected_ids: set[int] = set()

    for item in ranked:
        if all(abs(item[2] - chosen[2]) >= distance for chosen in selected):
            selected.append(item)
            selected_ids.add(item[0])
            if len(selected) >= max_items:
                break

    if len(selected) < max_items:
        for item in ranked:
            if item[0] in selected_ids:
                continue
            selected.append(item)
            selected_ids.add(item[0])
            if len(selected) >= max_items:
                break

    selected.sort(key=lambda item: (-item[3], item[0]))
    return [item[1] for item in selected]
