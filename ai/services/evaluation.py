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


def evaluate_ranked_candidates(predictions: Sequence[dict[str, Any]], ground_truth: Sequence[dict[str, Any]], *, top_k: int = 10, iou_threshold: float = 0.5) -> dict[str, Any]:
    """Match top-ranked predictions to unique labels and report quality/coverage diagnostics."""
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
    valid_predictions = [p for p in prediction_rows if _valid_interval(p)]
    ranked = sorted(valid_predictions, key=lambda item: _finite_score(item.get("score")), reverse=True)[:k]
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
        # A zero threshold must not turn disjoint intervals into true matches.
        if overlap > 0 and overlap >= threshold:
            matched_labels.add(index)
            matched_predictions += 1
            ious.append(overlap)

    precision = matched_predictions / len(ranked) if ranked else 0.0
    recall = matched_predictions / len(labels) if labels else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    pair_count = len(ranked) * (len(ranked) - 1) // 2
    duplicate_pairs = sum(
        1 for i, left in enumerate(ranked) for right in ranked[i + 1:]
        if threshold > 0 and interval_iou(left, right) >= threshold
    )
    centers = sorted((float(p["start"]) + float(p["end"])) / 2 for p in ranked)
    return {
        "predictionCount": len(prediction_rows),
        "validPredictionCount": len(valid_predictions),
        "groundTruthCount": len(labels),
        "evaluatedTopK": len(ranked),
        "iouThreshold": threshold,
        "matchedCount": matched_predictions,
        "precisionAtK": round(precision, 4),
        "recallAtK": round(recall, 4),
        "f1AtK": round(f1, 4),
        "meanMatchedIoU": round(sum(ious) / len(ious), 4) if ious else 0.0,
        "topKDuplicatePairRate": round(duplicate_pairs / pair_count, 4) if pair_count else 0.0,
        "topKTemporalSpreadSeconds": round(centers[-1] - centers[0], 3) if len(centers) > 1 else 0.0,
    }


def aggregate_evaluation_reports(reports: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Combine benchmark reports using count-weighted metrics and macro averages."""
    reports = [report for report in reports if isinstance(report, dict)]
    if not reports:
        return {
            "benchmarkCount": 0, "predictionCount": 0, "groundTruthCount": 0,
            "matchedCount": 0, "evaluatedTopK": 0, "precisionAtK": 0.0,
            "recallAtK": 0.0, "f1AtK": 0.0, "macroPrecisionAtK": 0.0,
            "macroRecallAtK": 0.0, "macroF1AtK": 0.0, "meanMatchedIoU": 0.0,
            "meanTopKDuplicatePairRate": 0.0, "meanTopKTemporalSpreadSeconds": 0.0,
        }
    prediction_count = sum(_nonnegative_int(r.get("predictionCount")) for r in reports)
    ground_truth_count = sum(_nonnegative_int(r.get("groundTruthCount")) for r in reports)
    matched_count = sum(_nonnegative_int(r.get("matchedCount")) for r in reports)
    evaluated_count = sum(_nonnegative_int(r.get("evaluatedTopK")) for r in reports)
    precision = matched_count / evaluated_count if evaluated_count else 0.0
    recall = matched_count / ground_truth_count if ground_truth_count else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    matched_iou_weight = sum(_bounded_metric(r.get("meanMatchedIoU")) * _nonnegative_int(r.get("matchedCount")) for r in reports)
    return {
        "benchmarkCount": len(reports), "predictionCount": prediction_count,
        "groundTruthCount": ground_truth_count, "matchedCount": matched_count,
        "evaluatedTopK": evaluated_count, "precisionAtK": round(precision, 4),
        "recallAtK": round(recall, 4), "f1AtK": round(f1, 4),
        "macroPrecisionAtK": round(sum(_bounded_metric(r.get("precisionAtK")) for r in reports) / len(reports), 4),
        "macroRecallAtK": round(sum(_bounded_metric(r.get("recallAtK")) for r in reports) / len(reports), 4),
        "macroF1AtK": round(sum(_bounded_metric(r.get("f1AtK")) for r in reports) / len(reports), 4),
        "meanMatchedIoU": round(matched_iou_weight / matched_count, 4) if matched_count else 0.0,
        "meanTopKDuplicatePairRate": round(sum(_bounded_metric(r.get("topKDuplicatePairRate")) for r in reports) / len(reports), 4),
        "meanTopKTemporalSpreadSeconds": round(sum(_nonnegative_float(r.get("topKTemporalSpreadSeconds")) for r in reports) / len(reports), 3),
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
        if math.isfinite(score):
            return score
    except (TypeError, ValueError, OverflowError):
        pass
    return 0.0


def _nonnegative_int(value: Any) -> int:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return 0
    return int(number) if math.isfinite(number) and number >= 0 else 0


def _nonnegative_float(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    return number if math.isfinite(number) and number >= 0 else 0.0


def _bounded_metric(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    if not math.isfinite(number):
        return 0.0
    return min(1.0, max(0.0, number))
