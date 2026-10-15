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
    except (KeyError, TypeError, ValueError):
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
    k = max(1, int(top_k))
    try:
        requested_threshold = float(iou_threshold)
    except (TypeError, ValueError, OverflowError):
        requested_threshold = 0.5
    threshold = min(1.0, max(0.0, requested_threshold)) if math.isfinite(requested_threshold) else 0.5
    ranked = sorted(
        (p for p in predictions if _valid_interval(p)),
        key=lambda item: _finite_score(item.get("score")),
        reverse=True,
    )[:k]
    labels = [g for g in ground_truth if _valid_interval(g)]

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
        "predictionCount": len(predictions),
        "validPredictionCount": sum(1 for p in predictions if _valid_interval(p)),
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
    """Combine benchmark reports using count-weighted metrics and macro averages."""
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

    prediction_count = sum(int(report.get("predictionCount", 0)) for report in reports)
    ground_truth_count = sum(int(report.get("groundTruthCount", 0)) for report in reports)
    matched_count = sum(int(report.get("matchedCount", 0)) for report in reports)
    evaluated_count = sum(int(report.get("evaluatedTopK", 0)) for report in reports)
    precision = matched_count / evaluated_count if evaluated_count else 0.0
    recall = matched_count / ground_truth_count if ground_truth_count else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    matched_iou_weight = sum(
        float(report.get("meanMatchedIoU", 0.0)) * int(report.get("matchedCount", 0))
        for report in reports
    )
    macro_precision = sum(float(r.get("precisionAtK", 0.0)) for r in reports) / len(reports)
    macro_recall = sum(float(r.get("recallAtK", 0.0)) for r in reports) / len(reports)
    macro_f1 = sum(float(r.get("f1AtK", 0.0)) for r in reports) / len(reports)

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


def _valid_interval(item: dict[str, Any]) -> bool:
    try:
        start, end = float(item["start"]), float(item["end"])
    except (KeyError, TypeError, ValueError):
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
