"""Offline evaluation metrics for human-labelled highlight ranges.

Ground truth is a list of timestamped moments; predictions are ranked candidates.
These metrics help compare changes without claiming that heuristics are accurate.
"""
from __future__ import annotations

from collections.abc import Sequence
import math
from typing import Any


def interval_iou(a: dict[str, Any], b: dict[str, Any]) -> float:
    try:
        a_start, a_end = float(a["start"]), float(a["end"])
        b_start, b_end = float(b["start"]), float(b["end"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return 0.0
    if not all(map(math.isfinite, (a_start, a_end, b_start, b_end))):
        return 0.0
    if a_end <= a_start or b_end <= b_start:
        return 0.0
    intersection = max(0.0, min(a_end, b_end) - max(a_start, b_start))
    union = max(a_end, b_end) - min(a_start, b_start)
    return intersection / union if union > 0 else 0.0


def evaluate_ranked_candidates(
    predictions: Sequence[dict[str, Any]],
    ground_truth: Sequence[dict[str, Any]],
    *,
    top_k: int = 10,
    iou_threshold: float = 0.5,
) -> dict[str, Any]:
    """Greedily match top-ranked predictions to unique labels and report metrics."""
    try:
        k = max(1, int(top_k))
    except (TypeError, ValueError, OverflowError):
        k = 10
    prediction_rows = predictions if isinstance(predictions, Sequence) and not isinstance(predictions, (str, bytes)) else ()
    label_rows = ground_truth if isinstance(ground_truth, Sequence) and not isinstance(ground_truth, (str, bytes)) else ()
    try:
        requested_threshold = float(iou_threshold)
    except (TypeError, ValueError, OverflowError):
        requested_threshold = 0.5
    threshold = min(1.0, max(0.0, requested_threshold)) if math.isfinite(requested_threshold) else 0.5
    ranked = sorted(
        (p for p in prediction_rows if _valid_interval(p)),
        key=lambda item: _finite_score(item.get("score")),
        reverse=True,
    )[:k]
    labels = [g for g in label_rows if _valid_interval(g)]

    matched_labels: set[int] = set()
    matched_predictions = 0
    ious: list[float] = []
    for prediction in ranked:
        options = [
            (interval_iou(prediction, label), index)
            for index, label in enumerate(labels)
            if index not in matched_labels
        ]
        if not options:
            continue
        overlap, index = max(options)
        if overlap >= threshold:
            matched_labels.add(index)
            matched_predictions += 1
            ious.append(overlap)

    precision = matched_predictions / len(ranked) if ranked else 0.0
    recall = matched_predictions / len(labels) if labels else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    return {
        "predictionCount": len(prediction_rows),
        "validPredictionCount": sum(1 for p in prediction_rows if _valid_interval(p)),
        "groundTruthCount": len(labels),
        "evaluatedTopK": len(ranked),
        "iouThreshold": threshold,
        "matchedCount": matched_predictions,
        "precisionAtK": round(precision, 4),
        "recallAtK": round(recall, 4),
        "f1AtK": round(f1, 4),
        "meanMatchedIoU": round(sum(ious) / len(ious), 4) if ious else 0.0,
    }


def aggregate_evaluation_reports(reports: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Combine benchmark reports using count-weighted metrics and macro averages.

    Malformed rows are ignored so one corrupt report cannot invalidate a benchmark.
    """
    reports = [report for report in reports if isinstance(report, dict)]
    if not reports:
        return {
            "benchmarkCount": 0,
            "predictionCount": 0,
            "groundTruthCount": 0,
            "matchedCount": 0,
            "evaluatedTopK": 0,
            "precisionAtK": 0.0,
            "recallAtK": 0.0,
            "f1AtK": 0.0,
            "macroPrecisionAtK": 0.0,
            "macroRecallAtK": 0.0,
            "macroF1AtK": 0.0,
            "meanMatchedIoU": 0.0,
        }

    prediction_count = sum(_nonnegative_int(report.get("predictionCount")) for report in reports)
    ground_truth_count = sum(_nonnegative_int(report.get("groundTruthCount")) for report in reports)
    matched_count = sum(_nonnegative_int(report.get("matchedCount")) for report in reports)
    evaluated_count = sum(_nonnegative_int(report.get("evaluatedTopK")) for report in reports)
    precision = matched_count / evaluated_count if evaluated_count else 0.0
    recall = matched_count / ground_truth_count if ground_truth_count else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    matched_iou_weight = sum(
        _bounded_metric(report.get("meanMatchedIoU")) * _nonnegative_int(report.get("matchedCount"))
        for report in reports
    )
    macro_precision = sum(_bounded_metric(r.get("precisionAtK")) for r in reports) / len(reports)
    macro_recall = sum(_bounded_metric(r.get("recallAtK")) for r in reports) / len(reports)
    macro_f1 = sum(_bounded_metric(r.get("f1AtK")) for r in reports) / len(reports)

    return {
        "benchmarkCount": len(reports),
        "predictionCount": prediction_count,
        "groundTruthCount": ground_truth_count,
        "matchedCount": matched_count,
        "evaluatedTopK": evaluated_count,
        "precisionAtK": round(precision, 4),
        "recallAtK": round(recall, 4),
        "f1AtK": round(f1, 4),
        "macroPrecisionAtK": round(macro_precision, 4),
        "macroRecallAtK": round(macro_recall, 4),
        "macroF1AtK": round(macro_f1, 4),
        "meanMatchedIoU": round(matched_iou_weight / matched_count, 4)
        if matched_count
        else 0.0,
    }


def _merged_coverage(intervals: list[tuple[float, float]]) -> float:
    """Total seconds covered by a set of intervals, counting overlaps once."""
    if not intervals:
        return 0.0
    ordered = sorted(intervals)
    total = 0.0
    current_start, current_end = ordered[0]
    for start, end in ordered[1:]:
        if start <= current_end:
            current_end = max(current_end, end)
        else:
            total += current_end - current_start
            current_start, current_end = start, end
    return total + (current_end - current_start)


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def selection_diagnostics(
    candidates: Sequence[dict[str, Any]],
    *,
    media_duration: float | None = None,
    top_k: int | None = None,
    duplicate_iou_threshold: float = 0.55,
    window_size_seconds: float = 120.0,
) -> dict[str, Any]:
    """Label-free structural diagnostics for a ranked candidate selection.

    These metrics describe the *shape* of a selection: how much of it is
    duplicated, how much of the source it covers, and whether the selected
    moments are concentrated in one narrow window. They require no human labels,
    but they are not a quality score. A selection can be perfectly spread and
    still be entirely uninteresting, so these numbers must never be presented as
    accuracy or as evidence that the chosen moments are good.

    Order is significant: candidates must be supplied in the order they are
    delivered to the user, and ``top_k`` measures that prefix. Sorting by score
    here would erase any upstream re-ranking (such as temporal diversification)
    and report the structure of a selection that is not the one being shipped.
    A duplicate is therefore counted against the earlier, higher-ranked rows.
    """
    # The order is meaningful: this measures the selection as delivered, so the
    # caller must pass a ranked list.
    valid = list(candidates) if isinstance(candidates, (list, tuple)) else []
    valid = [item for item in valid if _valid_interval(item)]

    if top_k is not None:
        try:
            limit = max(1, int(top_k))
        except (TypeError, ValueError, OverflowError):
            limit = len(valid)
        valid = valid[:limit]

    if not valid:
        return {
            "candidateCount": 0,
            "duplicateCount": 0,
            "duplicateRate": 0.0,
            "coverageSeconds": 0.0,
            "coverageRatio": 0.0,
            "occupiedWindowCount": 0,
            "totalWindowCount": 0,
            "windowOccupancyRatio": 0.0,
            "densestWindowShare": 0.0,
            "medianSpacingSeconds": 0.0,
            "meanScore": 0.0,
            "maxScore": 0.0,
        }

    try:
        overlap_threshold = float(duplicate_iou_threshold)
    except (TypeError, ValueError, OverflowError):
        overlap_threshold = 0.55
    overlap_threshold = min(1.0, max(0.0, overlap_threshold)) if math.isfinite(overlap_threshold) else 0.55

    try:
        window_size = float(window_size_seconds)
    except (TypeError, ValueError, OverflowError):
        window_size = 120.0
    window_size = max(1.0, window_size) if math.isfinite(window_size) else 120.0

    intervals = [(float(item["start"]), float(item["end"])) for item in valid]
    scores = [_finite_score(item.get("score")) for item in valid]

    # A candidate is a duplicate when a higher-scored candidate in the same
    # selection already covers it. Overlap is compared with the earlier
    # (higher-scored) rows only, so this cannot double-count a chain.
    duplicate_count = 0
    for index, candidate in enumerate(valid):
        if any(interval_iou(candidate, earlier) >= overlap_threshold for earlier in valid[:index]):
            duplicate_count += 1

    window_counts: dict[int, int] = {}
    for start, _ in intervals:
        window_index = int(start // window_size)
        window_counts[window_index] = window_counts.get(window_index, 0) + 1

    starts = sorted(start for start, _ in intervals)
    spacing = [b - a for a, b in zip(starts, starts[1:])]

    duration = None
    if media_duration is not None:
        try:
            parsed = float(media_duration)
        except (TypeError, ValueError, OverflowError):
            parsed = None
        if parsed is not None and math.isfinite(parsed) and parsed > 0:
            duration = parsed

    coverage = _merged_coverage(intervals)
    total_windows = int(math.ceil(duration / window_size)) if duration else 0

    return {
        "candidateCount": len(valid),
        "duplicateCount": duplicate_count,
        "duplicateRate": round(duplicate_count / len(valid), 4),
        "coverageSeconds": round(coverage, 3),
        "coverageRatio": round(min(1.0, coverage / duration), 4) if duration else 0.0,
        "occupiedWindowCount": len(window_counts),
        "totalWindowCount": total_windows,
        "windowOccupancyRatio": round(len(window_counts) / total_windows, 4) if total_windows else 0.0,
        "densestWindowShare": round(max(window_counts.values()) / len(valid), 4),
        "medianSpacingSeconds": round(_median(spacing), 3),
        "meanScore": round(sum(scores) / len(scores), 4),
        "maxScore": round(max(scores), 4),
    }


def aggregate_selection_diagnostics(reports: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Combine per-case structural diagnostics without letting bad rows dominate."""
    rows = [row for row in reports if isinstance(row, dict)]
    candidate_count = sum(_nonnegative_int(row.get("candidateCount")) for row in rows)
    duplicate_count = sum(_nonnegative_int(row.get("duplicateCount")) for row in rows)
    if not rows or not candidate_count:
        return {
            "caseCount": len(rows),
            "candidateCount": candidate_count,
            "duplicateRate": 0.0,
            "meanDensestWindowShare": 0.0,
            "meanCoverageRatio": 0.0,
            "meanWindowOccupancyRatio": 0.0,
        }
    return {
        "caseCount": len(rows),
        "candidateCount": candidate_count,
        "duplicateRate": round(duplicate_count / candidate_count, 4),
        "meanDensestWindowShare": round(
            sum(_bounded_metric(row.get("densestWindowShare")) for row in rows) / len(rows), 4
        ),
        "meanCoverageRatio": round(
            sum(_bounded_metric(row.get("coverageRatio")) for row in rows) / len(rows), 4
        ),
        "meanWindowOccupancyRatio": round(
            sum(_bounded_metric(row.get("windowOccupancyRatio")) for row in rows) / len(rows), 4
        ),
    }


def _valid_interval(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    try:
        start, end = float(item["start"]), float(item["end"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return False
    return math.isfinite(start) and math.isfinite(end) and start >= 0 and end > start


def _finite_score(value: Any) -> float:
    try:
        score = float(value)
        if score == score and abs(score) != float("inf"):
            return score
    except (TypeError, ValueError, OverflowError):
        pass
    return 0.0


def _nonnegative_int(value: Any) -> int:
    """Parse a non-negative count without allowing malformed data to crash aggregation."""
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return 0
    if not math.isfinite(number) or number < 0:
        return 0
    return int(number)


def _bounded_metric(value: Any) -> float:
    """Return a finite metric in [0, 1], defaulting invalid values to zero."""
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    if not math.isfinite(number):
        return 0.0
    return min(1.0, max(0.0, number))
