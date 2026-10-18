"""Safe interval deduplication and temporal selection for ranked clip candidates.

Two distinct concerns live here:

* ``deduplicate`` / ``select_candidates`` answer "is this the same moment again?"
  by comparing candidate intervals.
* ``enforce_temporal_diversity`` answers "are the chosen moments spread across the
  source, or all crammed into one short section?" by re-ranking.

Neither of them measures whether a moment is *interesting*. They are safety and
shape guarantees for a ranking that upstream scoring produced.
"""
from __future__ import annotations

import math
from typing import Any

# A clip shorter than this cannot carry a hook plus its payoff; a short-form clip
# longer than this stops being a clip. Both are conservative deliberately: the
# selector must not silently rewrite a pipeline's output, and callers that need a
# different policy pass their own bounds.
DEFAULT_MIN_CLIP_SECONDS = 3.0
DEFAULT_MAX_CLIP_SECONDS = 90.0
DEFAULT_IOU_THRESHOLD = 0.55
# Intersection over the *shorter* interval. Much stricter than IoU for containment:
# a 10 s window inside a 60 s window has an IoU of only 0.17 but shares 100% of the
# shorter window, so it is the same moment and must not be selected twice.
DEFAULT_OVERLAP_THRESHOLD = 0.8

_REASON_KEYS = ("malformed", "invalid_interval", "too_short", "near_duplicate")


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


def _overlap_ratio(a: dict, b: dict) -> float:
    """Intersection divided by the shorter interval (containment-sensitive)."""
    first, second = _interval(a), _interval(b)
    if first is None or second is None:
        return 0.0
    left = max(first[0], second[0])
    right = min(first[1], second[1])
    intersection = max(0.0, right - left)
    shortest = min(first[1] - first[0], second[1] - second[0])
    return intersection / shortest if shortest > 0 else 0.0


def _clamp_unit(value: Any, fallback: float) -> float:
    number = _finite(value)
    if number is None:
        return fallback
    return min(1.0, max(0.0, number))


def _optional_seconds(value: Any) -> float | None:
    """Return a positive bound in seconds, or None when the bound is disabled."""
    if value is None:
        return None
    number = _finite(value)
    if number is None or number <= 0:
        return None
    return number


def _describe(interval: tuple[float, float]) -> str:
    return f"{interval[0]:.2f}-{interval[1]:.2f}s"


def _rejection(candidate: Any, reason: str, detail: str | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {"reason": reason}
    if isinstance(candidate, dict):
        interval = _interval(candidate)
        if interval is not None:
            row["start"] = round(interval[0], 3)
            row["end"] = round(interval[1], 3)
            row["duration"] = round(interval[1] - interval[0], 3)
        score = _finite(candidate.get("score"))
        if score is not None:
            row["score"] = round(score, 2)
    if detail:
        row["detail"] = detail
    return row


def select_candidates(
    candidates: Any,
    *,
    min_duration: float | None = DEFAULT_MIN_CLIP_SECONDS,
    max_duration: float | None = DEFAULT_MAX_CLIP_SECONDS,
    iou_threshold: float = DEFAULT_IOU_THRESHOLD,
    overlap_threshold: float | None = DEFAULT_OVERLAP_THRESHOLD,
    max_rejections: int = 50,
) -> dict[str, Any]:
    """Select a duration-bounded, non-repetitive subset of clip candidates.

    Returns ``{"selected": [...], "rejected": [...], "report": {...}}``.

    The kept set is order-independent: candidates are ranked by score (ties broken
    by earlier start, then earlier end) so a tied ranking is deterministic. The
    highest-scoring valid window wins each overlapping group. Rejections carry a
    human-readable reason, so a selection can be explained after the fact instead
    of candidates vanishing silently.

    Bounds:
      ``min_duration``      drop clips shorter than this (None/0 disables)
      ``max_duration``      trim clips longer than this, keeping the start (None/0 disables)
      ``iou_threshold``     treat an interval pair as duplicate at/above this IoU
      ``overlap_threshold`` also treat containment at/above this intersection-over-shorter
                            ratio as duplicate (None/0 disables the containment check)
    """
    minimum = _optional_seconds(min_duration)
    maximum = _optional_seconds(max_duration)
    if minimum is not None and maximum is not None and maximum < minimum:
        # A ceiling below the floor is contradictory. Honour the floor so the
        # policy degrades to "no clip shorter than the minimum" instead of
        # emitting a clip shorter than the minimum it was asked to enforce.
        maximum = minimum
    iou = _clamp_unit(iou_threshold, DEFAULT_IOU_THRESHOLD)
    # None/0 disables the containment check; report it as 0.0 so a reader can tell
    # "disabled" apart from "enabled with a threshold".
    overlap = _optional_seconds(overlap_threshold)
    if overlap is not None:
        overlap = _clamp_unit(overlap_threshold, DEFAULT_OVERLAP_THRESHOLD)

    report: dict[str, Any] = {
        "considered": 0,
        "selectedCount": 0,
        "rejectedCount": 0,
        "rejectedByReason": {key: 0 for key in _REASON_KEYS},
        "trimmedCount": 0,
        "minDurationSeconds": minimum,
        "maxDurationSeconds": maximum,
        "iouThreshold": iou,
        "overlapThreshold": overlap if overlap is not None else 0.0,
        "rejections": [],
        "trims": [],
    }
    if not isinstance(candidates, (list, tuple)):
        return {"selected": [], "rejected": [], "report": report}

    try:
        rejection_cap = max(0, int(max_rejections))
    except (TypeError, ValueError, OverflowError):
        rejection_cap = 50

    report["considered"] = len(candidates)

    rejected: list[dict[str, Any]] = []
    valid: list[dict[str, Any]] = []
    trims: list[dict[str, Any]] = []
    counts = report["rejectedByReason"]

    def _reject(candidate: Any, reason: str, detail: str | None = None) -> None:
        counts[reason] = counts.get(reason, 0) + 1
        if len(rejected) < rejection_cap:
            rejected.append(_rejection(candidate, reason, detail))

    for raw in candidates:
        if not isinstance(raw, dict):
            _reject(raw, "malformed", "candidate must be an object")
            continue
        interval = _interval(raw)
        item = dict(raw)
        score = _finite(item.get("score"))
        item["score"] = score if score is not None else 0.0
        if interval is None:
            _reject(
                item,
                "invalid_interval",
                "start/end must be finite with start >= 0 and end > start",
            )
            continue

        start, end = interval
        duration = end - start
        if minimum is not None and duration < minimum:
            _reject(
                item,
                "too_short",
                f"duration {duration:.2f}s is below the {minimum:g}s minimum",
            )
            continue
        if maximum is not None and duration > maximum:
            trimmed_end = start + maximum
            trims.append({
                "start": round(start, 3),
                "originalEnd": round(end, 3),
                "end": round(trimmed_end, 3),
                "score": round(item["score"], 2),
            })
            # Record the trim on the candidate itself so a shipped clip whose end
            # differs from the model's proposal is self-describing. Copy the nested
            # dict: the row above is a shallow copy and must not mutate caller data.
            existing_features = item.get("features")
            features = dict(existing_features) if isinstance(existing_features, dict) else {}
            features["selection"] = {
                "trimmedToMaxDuration": round(maximum, 3),
                "originalEnd": round(end, 3),
            }
            item["features"] = features
            item["end"] = round(trimmed_end, 3)
            item["duration"] = round(maximum, 3)
            valid.append(item)
            continue
        valid.append(item)

    kept: list[dict[str, Any]] = []
    ranked = sorted(
        valid,
        key=lambda row: (
            -row["score"],
            (_interval(row) or (0.0, 0.0))[0],
            (_interval(row) or (0.0, 0.0))[1],
        ),
    )
    for item in ranked:
        duplicate_of: tuple[tuple[float, float], str] | None = None
        for existing in kept:
            existing_interval = _interval(existing)
            if existing_interval is None:  # pragma: no cover - kept rows are valid
                continue
            overlap_iou = _iou(item, existing)
            if overlap_iou >= iou:
                duplicate_of = (existing_interval, f"IoU {overlap_iou:.2f} >= {iou:.2f}")
                break
            if overlap is not None:
                ratio = _overlap_ratio(item, existing)
                if ratio >= overlap:
                    duplicate_of = (
                        existing_interval,
                        f"contains/overlaps {ratio:.2f} of the shorter window >= {overlap:.2f}",
                    )
                    break
        if duplicate_of is None:
            kept.append(item)
            continue
        existing_interval, detail = duplicate_of
        _reject(
            item,
            "near_duplicate",
            f"shows the same moment as the kept {_describe(existing_interval)} ({detail})",
        )

    report["selectedCount"] = len(kept)
    report["rejectedCount"] = report["considered"] - len(kept)
    report["trimmedCount"] = len(trims)
    report["rejections"] = rejected
    report["trims"] = trims[:rejection_cap]
    return {"selected": kept, "rejected": rejected, "report": report}


def deduplicate(
    candidates: list[dict],
    threshold: float = DEFAULT_IOU_THRESHOLD,
    overlap_threshold: float | None = DEFAULT_OVERLAP_THRESHOLD,
) -> list[dict]:
    """Keep the highest-scoring valid candidate from each overlapping interval group.

    A pair counts as the same moment when its IoU reaches ``threshold`` *or* when
    one interval contains ``overlap_threshold`` of the shorter one. The containment
    test is what stops a short clip that sits inside a long one from being shipped
    alongside it: IoU alone scores that pair ~0.17 and keeps both.

    Invalid/non-finite intervals are dropped here as a final defensive boundary;
    the candidate contract remains responsible for normalizing API output.
    """
    return select_candidates(
        candidates,
        min_duration=None,
        max_duration=None,
        iou_threshold=threshold,
        overlap_threshold=overlap_threshold,
    )["selected"]


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
