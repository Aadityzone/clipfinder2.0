"""Structural diagnostics for candidate selections.

These are label-free shape metrics. The tests below assert the measurements are
correct and finite; they do not assert that a spread selection is a *better*
selection, because that requires human labels.
"""
import math

from ai.services.evaluation import (
    aggregate_selection_diagnostics,
    selection_diagnostics,
)


def test_empty_and_malformed_input_reports_zeroed_diagnostics():
    for payload in (None, [], "nope", [None, "x", {"start": "bad", "end": 3}]):
        result = selection_diagnostics(payload)  # type: ignore[arg-type]
        assert result["candidateCount"] == 0
        assert result["duplicateRate"] == 0.0
        assert result["densestWindowShare"] == 0.0


def test_all_metrics_are_finite_and_bounded():
    rows = [
        {"start": float("nan"), "end": 10, "score": float("inf")},
        {"start": 0, "end": 20, "score": float("nan")},
        {"start": 10, "end": 40, "score": 50},
        {"start": 100, "end": 130, "score": 80},
    ]
    result = selection_diagnostics(rows, media_duration=200.0)

    assert result["candidateCount"] == 3
    for key in ("duplicateRate", "coverageRatio", "windowOccupancyRatio", "densestWindowShare"):
        assert math.isfinite(result[key]), key
        assert 0.0 <= result[key] <= 1.0, key


def test_clustered_selection_reports_concentration():
    # Five candidates packed into the first two minutes of a one-hour source.
    rows = [{"start": 5.0 * index, "end": 5.0 * index + 10.0, "score": 90 - index} for index in range(5)]
    result = selection_diagnostics(rows, media_duration=3600.0)

    assert result["candidateCount"] == 5
    assert result["occupiedWindowCount"] == 1
    assert result["totalWindowCount"] == 30
    assert result["densestWindowShare"] == 1.0
    assert result["windowOccupancyRatio"] < 0.05
    assert result["coverageRatio"] < 0.05


def test_spread_selection_reports_higher_window_occupancy():
    rows = [{"start": 300.0 * index, "end": 300.0 * index + 30.0, "score": 60} for index in range(6)]
    result = selection_diagnostics(rows, media_duration=1800.0)

    assert result["candidateCount"] == 6
    assert result["occupiedWindowCount"] == 6
    assert result["densestWindowShare"] < 0.5
    assert result["medianSpacingSeconds"] == 300.0


def test_diversity_ordering_reduces_densest_window_share_of_the_top_selection():
    """The pipeline's diversity step should spread the top-ranked prefix.

    Diversity only reorders candidates (it drops none), so the composition of the
    full set is unchanged. The user-visible effect is on the top-K prefix: the
    highest-ranked rows are no longer all drawn from one dense window.
    """
    from ai.services.dedup import enforce_temporal_diversity

    clustered = [
        {"start": 10.0, "end": 25.0, "score": 95.0},
        {"start": 40.0, "end": 55.0, "score": 94.0},
        {"start": 70.0, "end": 85.0, "score": 93.0},
        {"start": 900.0, "end": 915.0, "score": 60.0},
    ]
    before = selection_diagnostics(clustered, media_duration=1800.0, top_k=3)
    diversified = enforce_temporal_diversity(clustered)
    after = selection_diagnostics(diversified, media_duration=1800.0, top_k=3)

    assert before["densestWindowShare"] == 1.0
    assert after["densestWindowShare"] < before["densestWindowShare"]
    # Diversity is an ordering change, so membership must be preserved exactly.
    assert {row["start"] for row in diversified} == {row["start"] for row in clustered}


def test_duplicate_overlaps_are_counted_against_higher_scored_rows():
    rows = [
        {"start": 0.0, "end": 20.0, "score": 90.0},
        {"start": 2.0, "end": 18.0, "score": 85.0},  # contained in the first
        {"start": 60.0, "end": 80.0, "score": 80.0},
    ]
    result = selection_diagnostics(rows)

    assert result["duplicateCount"] == 1
    assert result["duplicateRate"] == round(1 / 3, 4)


def test_non_overlapping_candidates_are_not_duplicates():
    rows = [
        {"start": 0.0, "end": 10.0, "score": 90.0},
        {"start": 20.0, "end": 30.0, "score": 80.0},
        {"start": 40.0, "end": 50.0, "score": 70.0},
    ]
    assert selection_diagnostics(rows)["duplicateRate"] == 0.0


def test_coverage_counts_overlapping_seconds_once():
    rows = [
        {"start": 0.0, "end": 60.0, "score": 90.0},
        {"start": 30.0, "end": 90.0, "score": 80.0},
    ]
    result = selection_diagnostics(rows, media_duration=180.0)

    assert result["coverageSeconds"] == 90.0
    assert result["coverageRatio"] == 0.5


def test_coverage_is_zero_without_a_usable_duration():
    rows = [{"start": 0.0, "end": 10.0, "score": 90.0}]
    for duration in (None, 0, -5, float("nan"), "abc"):
        result = selection_diagnostics(rows, media_duration=duration)
        assert result["coverageRatio"] == 0.0
        assert result["totalWindowCount"] == 0


def test_top_k_limits_the_measured_selection():
    rows = [{"start": 10.0 * index, "end": 10.0 * index + 5.0, "score": 50} for index in range(5)]
    assert selection_diagnostics(rows, top_k=2)["candidateCount"] == 2
    assert selection_diagnostics(rows, top_k=999)["candidateCount"] == 5


def test_aggregate_diagnostics_ignores_malformed_reports():
    reports = [
        {"candidateCount": 4, "duplicateCount": 1, "densestWindowShare": 1.0,
         "coverageRatio": 0.1, "windowOccupancyRatio": 0.05},
        None,
        "bad",
        {"candidateCount": "x", "duplicateCount": float("nan"), "densestWindowShare": "Z"},
    ]
    result = aggregate_selection_diagnostics(reports)

    assert result["caseCount"] == 2
    assert result["candidateCount"] == 4
    assert result["duplicateRate"] == 0.25
    assert math.isfinite(result["meanDensestWindowShare"])


def test_aggregate_diagnostics_on_empty_input_is_zeroed():
    assert aggregate_selection_diagnostics([])["candidateCount"] == 0
    assert aggregate_selection_diagnostics([])["duplicateRate"] == 0.0
