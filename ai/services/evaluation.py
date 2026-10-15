"""Small, dependency-free evaluation metrics for highlight candidate quality.

Ground-truth moments use {"start": float, "end": float, optional "genre": str}.
Predictions use the same interval fields and may include a score and genre. Metrics
are for labelled offline fixtures, not a claim that any model is good.
"""
from __future__ import annotations

import math


def _interval(item: dict) -> tuple[float, float] | None:
    if not isinstance(item, dict):
        return None
    if isinstance(item.get("start"), bool) or isinstance(item.get("end"), bool):
        return None
    try:
        start, end = float(item["start"]), float(item["end"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end <= start:
        return None
    return start, end


def _genre(item: dict) -> str:
    return str(item.get("genre", "unknown")).strip().lower() or "unknown"


def _score(item: dict) -> float:
    value = item.get("score", 0)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    parsed = float(value)
    return parsed if math.isfinite(parsed) else 0.0


def temporal_iou(left: dict, right: dict) -> float:
    """Intersection-over-union for two valid temporal intervals; invalid is zero."""
    a, b = _interval(left), _interval(right)
    if a is None or b is None:
        return 0.0
    intersection = max(0.0, min(a[1], b[1]) - max(a[0], b[0]))
    union = max(a[1], b[1]) - min(a[0], b[0])
    return intersection / union if union > 0 else 0.0


def evaluate_candidates(predictions: list[dict], ground_truth: list[dict],
                        top_k: int = 10, iou_threshold: float = 0.5) -> dict:
    """Return precision@k, recall@k, and mean best-IoU using one-to-one matching."""
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
        raise ValueError("top_k must be an integer of at least 1")
    if isinstance(iou_threshold, bool) or not math.isfinite(float(iou_threshold)) or not 0 <= iou_threshold <= 1:
        raise ValueError("iou_threshold must be between 0 and 1")

    valid_truth = [item for item in ground_truth if _interval(item) is not None]
    valid_predictions = [item for item in predictions if _interval(item) is not None]
    valid_predictions.sort(key=_score, reverse=True)
    selected = valid_predictions[:top_k]
    unmatched_truth = set(range(len(valid_truth)))
    matches = []
    for prediction in selected:
        options = [(temporal_iou(prediction, valid_truth[index]), index)
                   for index in unmatched_truth]
        if not options:
            matches.append(0.0)
            continue
        best_iou, best_index = max(options, default=(0.0, -1))
        matches.append(best_iou)
        if best_iou >= iou_threshold:
            unmatched_truth.remove(best_index)

    true_positives = len(valid_truth) - len(unmatched_truth)
    precision = true_positives / top_k
    recall = true_positives / len(valid_truth) if valid_truth else 0.0
    mean_best_iou = sum(matches) / len(matches) if matches else 0.0
    return {
        "predictionCount": len(valid_predictions),
        "groundTruthCount": len(valid_truth),
        "topK": top_k,
        "iouThreshold": iou_threshold,
        "truePositivesAtK": true_positives,
        "precisionAtK": round(precision, 4),
        "recallAtK": round(recall, 4),
        "meanBestIoUAtK": round(mean_best_iou, 4),
    }


def evaluate_by_genre(predictions: list[dict], ground_truth: list[dict],
                      top_k: int = 10, iou_threshold: float = 0.5) -> dict:
    """Compute per-genre recall and macro recall without cross-genre leakage.

    When a prediction has a genre label, it is evaluated only against that genre.
    Unlabelled predictions are retained as genre-agnostic proposals.
    """
    valid_truth = [item for item in ground_truth if _interval(item) is not None]
    genres = sorted({_genre(item) for item in valid_truth})
    per_genre = {}
    for genre in genres:
        truth = [item for item in valid_truth if _genre(item) == genre]
        relevant_predictions = [
            item for item in predictions
            if not isinstance(item, dict)
            or not item.get("genre")
            or _genre(item) == genre
        ]
        metrics = evaluate_candidates(relevant_predictions, truth, top_k, iou_threshold)
        per_genre[genre] = metrics["recallAtK"]
    macro = sum(per_genre.values()) / len(per_genre) if per_genre else 0.0
    return {"perGenreRecallAtK": per_genre, "macroRecallAtK": round(macro, 4)}
