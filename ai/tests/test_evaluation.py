from ai.services.evaluation import (
    aggregate_evaluation_reports,
    evaluate_ranked_candidates,
    interval_iou,
)


def test_interval_iou_for_overlapping_and_disjoint_ranges():
    assert interval_iou({"start": 0, "end": 10}, {"start": 5, "end": 15}) == 1 / 3
    assert interval_iou({"start": 0, "end": 3}, {"start": 5, "end": 8}) == 0


def test_ranked_evaluation_matches_each_label_at_most_once():
    predictions = [
        {"start": 0, "end": 10, "score": 90},
        {"start": 1, "end": 9, "score": 80},
        {"start": 30, "end": 40, "score": 70},
    ]
    labels = [{"start": 0, "end": 10}, {"start": 30, "end": 40}]
    result = evaluate_ranked_candidates(predictions, labels, top_k=3, iou_threshold=0.5)
    assert result["matchedCount"] == 2
    assert result["precisionAtK"] == round(2 / 3, 4)
    assert result["recallAtK"] == 1.0
    assert result["f1AtK"] == round(0.8, 4)


def test_evaluation_handles_empty_and_invalid_inputs():
    result = evaluate_ranked_candidates(
        [{"start": 2, "end": 2, "score": 100}, {"start": 0, "end": 5, "score": 20}],
        [],
    )
    assert result["validPredictionCount"] == 1
    assert result["groundTruthCount"] == 0
    assert result["precisionAtK"] == 0
    assert result["recallAtK"] == 0


def test_aggregate_reports_are_count_weighted_and_include_macro_metrics():
    reports = [
        {"predictionCount": 2, "groundTruthCount": 1, "matchedCount": 1,
         "evaluatedTopK": 2, "precisionAtK": 0.5, "recallAtK": 1.0,
         "f1AtK": round(2 / 3, 4), "meanMatchedIoU": 0.8},
        {"predictionCount": 10, "groundTruthCount": 4, "matchedCount": 2,
         "evaluatedTopK": 5, "precisionAtK": 0.4, "recallAtK": 0.5,
         "f1AtK": round(4 / 9, 4), "meanMatchedIoU": 0.6},
    ]
    result = aggregate_evaluation_reports(reports)
    assert result["benchmarkCount"] == 2
    assert result["matchedCount"] == 3
    assert result["precisionAtK"] == round(3 / 7, 4)
    assert result["recallAtK"] == 0.6
    assert result["macroPrecisionAtK"] == 0.45
    assert result["meanMatchedIoU"] == round((0.8 + 1.2) / 3, 4)


def test_aggregate_empty_reports_is_safe():
    result = aggregate_evaluation_reports([])
    assert result["benchmarkCount"] == 0
    assert result["f1AtK"] == 0


def test_evaluation_rejects_non_finite_timestamps_and_thresholds():
    predictions = [
        {"start": float("nan"), "end": 10, "score": 100},
        {"start": 0, "end": float("inf"), "score": 90},
        {"start": 1, "end": 4, "score": 80},
    ]
    labels = [
        {"start": float("nan"), "end": 3},
        {"start": 1, "end": float("inf")},
        {"start": 1, "end": 4},
    ]
    result = evaluate_ranked_candidates(predictions, labels, top_k=10, iou_threshold=float("nan"))
    assert result["validPredictionCount"] == 1
    assert result["groundTruthCount"] == 1
    assert result["iouThreshold"] == 0.5
    assert result["matchedCount"] == 1


def test_interval_iou_rejects_non_finite_boundaries():
    assert interval_iou({"start": 0, "end": float("inf")}, {"start": 0, "end": 5}) == 0.0


def test_evaluator_ignores_non_object_rows_and_non_finite_scores():
    result = evaluate_ranked_candidates(
        [None, "bad", {"start": 0, "end": 5, "score": float("nan")},
         {"start": 1, "end": 4, "score": 90}],
        [None, {"start": 1, "end": 4}], top_k=10,
    )
    assert result["predictionCount"] == 4
    assert result["validPredictionCount"] == 2
    assert result["groundTruthCount"] == 1
    assert result["matchedCount"] == 1


def test_aggregate_ignores_malformed_reports_and_clamps_metrics():
    result = aggregate_evaluation_reports([
        None,
        {"predictionCount": "bad", "groundTruthCount": -2, "matchedCount": float("inf"),
         "evaluatedTopK": 0, "precisionAtK": float("nan"), "recallAtK": 2,
         "f1AtK": -1, "meanMatchedIoU": "not-a-number"},
        {"predictionCount": 3, "groundTruthCount": 2, "matchedCount": 1,
         "evaluatedTopK": 2, "precisionAtK": 0.5, "recallAtK": 0.5,
         "f1AtK": 0.5, "meanMatchedIoU": 0.75},
    ])
    assert result["benchmarkCount"] == 2
    assert result["predictionCount"] == 3
    assert result["groundTruthCount"] == 2
    assert result["matchedCount"] == 1
    assert result["macroPrecisionAtK"] == 0.25
    assert result["macroRecallAtK"] == 0.75
    assert result["macroF1AtK"] == 0.25
    assert result["meanMatchedIoU"] == 0.75


def test_evaluation_handles_missing_or_non_sequence_collections():
    assert evaluate_ranked_candidates(None, None)["predictionCount"] == 0
    assert evaluate_ranked_candidates("not predictions", {"start": 0, "end": 1})["groundTruthCount"] == 0


def test_evaluation_handles_unconvertible_extreme_values():
    class HugeNumber:
        def __float__(self):
            raise OverflowError("too large")

    assert interval_iou({"start": HugeNumber(), "end": 3}, {"start": 0, "end": 3}) == 0.0
    result = evaluate_ranked_candidates([{"start": HugeNumber(), "end": 3}], [{"start": 0, "end": 3}])
    assert result["validPredictionCount"] == 0


def test_evaluation_reports_duplicate_rate_and_temporal_spread():
    predictions = [
        {"start": 0, "end": 10, "score": 90},
        {"start": 1, "end": 9, "score": 80},
        {"start": 100, "end": 110, "score": 70},
    ]
    result = evaluate_ranked_candidates(predictions, [], top_k=3, iou_threshold=0.5)
    assert result["topKDuplicatePairRate"] == round(1 / 3, 4)
    assert result["topKTemporalSpreadSeconds"] == 100.0


def test_aggregate_includes_duplicate_rate_and_temporal_spread():
    result = aggregate_evaluation_reports([
        {"topKDuplicatePairRate": 0.25, "topKTemporalSpreadSeconds": 100},
        {"topKDuplicatePairRate": 0.75, "topKTemporalSpreadSeconds": 300},
    ])
    assert result["meanTopKDuplicatePairRate"] == 0.5
    assert result["meanTopKTemporalSpreadSeconds"] == 200.0
