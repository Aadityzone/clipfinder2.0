"""Deterministic tests for temporal clip-candidate selection.

Scope: these cases assert *structural* guarantees of the selector - that the same
moment is not shipped twice, that clip durations stay inside bounds, that moments
spread across a long source survive, that a tied ranking is reproducible, and that
every rejection carries a reason.

They are synthetic. Passing them proves the selection logic behaves as specified;
it does NOT measure whether any selected moment is interesting in a real video. No
human-labelled evaluation data exists in this repo, so real-world highlight quality
remains unmeasured and must not be inferred from this file.
"""
from ai.services.dedup import (
    DEFAULT_MAX_CLIP_SECONDS,
    DEFAULT_MIN_CLIP_SECONDS,
    deduplicate,
    enforce_temporal_diversity,
    select_candidates,
)


# --------------------------------------------------------------------------------------
# Several candidates describing the same moment
# --------------------------------------------------------------------------------------

def test_candidates_describing_the_same_moment_collapse_to_the_best_one():
    candidates = [
        {"start": 10.0, "end": 40.0, "score": 91.0},
        {"start": 12.0, "end": 38.0, "score": 88.0},
        {"start": 11.0, "end": 39.0, "score": 95.0},
        {"start": 13.0, "end": 41.0, "score": 80.0},
    ]

    result = select_candidates(candidates)

    assert [row["start"] for row in result["selected"]] == [11.0]
    assert result["selected"][0]["score"] == 95.0
    assert result["report"]["rejectedByReason"]["near_duplicate"] == 3
    assert {row["reason"] for row in result["rejected"]} == {"near_duplicate"}


def test_a_contained_clip_is_a_duplicate_even_though_iou_is_low():
    """IoU alone misses containment: a 10 s clip inside a 60 s clip scores only 0.17."""
    outer = {"start": 0.0, "end": 60.0, "score": 90.0}
    inner = {"start": 25.0, "end": 35.0, "score": 60.0}

    # With containment matching disabled, IoU keeps both windows.
    assert len(deduplicate([outer, inner], overlap_threshold=None)) == 2

    # Containment-aware selection keeps only the higher-scoring window.
    result = select_candidates([outer, inner])
    assert [row["start"] for row in result["selected"]] == [0.0]
    assert result["rejected"][0]["reason"] == "near_duplicate"
    assert "same moment" in result["rejected"][0]["detail"]


# --------------------------------------------------------------------------------------
# Genuinely different moments / spread across the source
# --------------------------------------------------------------------------------------

def test_genuinely_different_moments_are_all_kept():
    candidates = [
        {"start": 0.0, "end": 30.0, "score": 70.0},
        {"start": 60.0, "end": 90.0, "score": 80.0},
        {"start": 150.0, "end": 180.0, "score": 90.0},
        {"start": 300.0, "end": 330.0, "score": 60.0},
    ]

    result = select_candidates(candidates, max_duration=120.0)

    assert len(result["selected"]) == 4
    assert result["report"]["rejectedCount"] == 0
    assert result["report"]["trimmedCount"] == 0


def test_moments_across_beginning_middle_and_end_survive():
    candidates = [
        {"start": 0.0, "end": 20.0, "score": 88.0},       # beginning
        {"start": 600.0, "end": 620.0, "score": 84.0},    # middle
        {"start": 1180.0, "end": 1200.0, "score": 86.0},  # end
    ]

    result = select_candidates(candidates)

    assert len(result["selected"]) == 3
    assert sorted(row["start"] for row in result["selected"]) == [0.0, 600.0, 1180.0]
    # The diversity pass agrees they are not clustered: all three survive it.
    assert len(enforce_temporal_diversity(result["selected"])) == 3


# --------------------------------------------------------------------------------------
# Invalid timestamps / zero-length clips
# --------------------------------------------------------------------------------------

def test_invalid_and_zero_length_clips_are_rejected_with_reasons():
    candidates = [
        {"start": 11.0, "end": 11.0, "score": 90.0},          # zero length
        {"start": 30.0, "end": 20.0, "score": 90.0},          # inverted
        {"start": float("nan"), "end": 40.0, "score": 90.0},  # non-finite start
        {"start": -5.0, "end": 10.0, "score": 90.0},          # negative start
        {"start": 100.0, "end": 130.0, "score": 70.0},        # the only usable window
    ]

    result = select_candidates(candidates)

    assert [row["start"] for row in result["selected"]] == [100.0]
    assert result["report"]["rejectedByReason"]["invalid_interval"] == 4
    assert result["report"]["considered"] == 5
    assert result["report"]["selectedCount"] == 1
    assert all("detail" in row for row in result["rejected"])


def test_malformed_rows_are_rejected_with_a_reason_instead_of_crashing():
    result = select_candidates([
        None,
        "bad row",
        42,
        {"start": "not a number", "end": 5, "score": 10},
        {"start": 0.0, "end": 10.0, "score": 10.0},
    ])

    assert [row["start"] for row in result["selected"]] == [0.0]
    assert result["report"]["rejectedByReason"]["malformed"] == 3
    assert result["report"]["rejectedByReason"]["invalid_interval"] == 1


# --------------------------------------------------------------------------------------
# Empty input / tied scores
# --------------------------------------------------------------------------------------

def test_empty_and_non_sequence_inputs_select_nothing():
    for payload in ([], (), None, "nope", {"start": 0.0, "end": 5.0}):
        result = select_candidates(payload)
        assert result["selected"] == []
        assert result["rejected"] == []
        assert result["report"]["considered"] == 0
        assert result["report"]["selectedCount"] == 0


def test_tied_scores_are_resolved_deterministically():
    candidates = [
        {"start": 200.0, "end": 220.0, "score": 50.0},
        {"start": 80.0, "end": 100.0, "score": 50.0},
        {"start": 20.0, "end": 40.0, "score": 50.0},
    ]

    forward = select_candidates(candidates)
    backward = select_candidates(list(reversed(candidates)))

    assert [row["start"] for row in forward["selected"]] == [20.0, 80.0, 200.0]
    assert forward["selected"] == backward["selected"]

    # Same score and same start: the earlier end wins, and the loser is rejected.
    nested = [
        {"start": 10.0, "end": 30.0, "score": 50.0},
        {"start": 10.0, "end": 25.0, "score": 50.0},
    ]
    picked = select_candidates(nested)["selected"]
    assert len(picked) == 1
    assert picked[0]["end"] == 25.0


# --------------------------------------------------------------------------------------
# Repetition that plain top-k produces but the selector avoids
# --------------------------------------------------------------------------------------

def test_selector_avoids_the_repetition_a_plain_top_k_would_ship():
    """Synthetic worst case: the four highest scores all describe one 30 s window."""
    candidates = [
        {"start": 100.0, "end": 130.0, "score": 99.0},
        {"start": 102.0, "end": 132.0, "score": 98.0},
        {"start": 104.0, "end": 134.0, "score": 97.0},
        {"start": 106.0, "end": 128.0, "score": 96.0},
        {"start": 500.0, "end": 530.0, "score": 40.0},
    ]

    naive_top_three = sorted(candidates, key=lambda row: -row["score"])[:3]
    # Nothing in the naive top three is the second moment - it is three copies of one.
    assert 500.0 not in [row["start"] for row in naive_top_three]

    selected = select_candidates(candidates)["selected"]
    assert [row["start"] for row in selected] == [100.0, 500.0]


# --------------------------------------------------------------------------------------
# Duration bounds
# --------------------------------------------------------------------------------------

def test_clips_below_the_minimum_duration_are_dropped():
    candidates = [
        {"start": 0.0, "end": 1.2, "score": 95.0},
        {"start": 30.0, "end": 31.0, "score": 94.0},
        {"start": 60.0, "end": 70.0, "score": 50.0},
    ]

    result = select_candidates(candidates, min_duration=3.0)

    assert [row["start"] for row in result["selected"]] == [60.0]
    assert result["report"]["rejectedByReason"]["too_short"] == 2
    assert "below the 3s minimum" in result["rejected"][0]["detail"]
    assert len(select_candidates(
        candidates, min_duration=None, max_duration=None
    )["selected"]) == 3


def test_overlong_clip_is_trimmed_and_the_trim_is_recorded():
    candidates = [{"start": 10.0, "end": 400.0, "score": 80.0, "features": {"sceneHits": 1}}]

    result = select_candidates(candidates, max_duration=90.0)

    assert len(result["selected"]) == 1
    kept = result["selected"][0]
    assert (kept["start"], kept["end"]) == (10.0, 100.0)
    assert kept["duration"] == 90.0
    assert kept["features"]["sceneHits"] == 1
    assert kept["features"]["selection"] == {
        "trimmedToMaxDuration": 90.0,
        "originalEnd": 400.0,
    }
    assert result["report"]["trimmedCount"] == 1
    assert result["report"]["trims"][0] == {
        "start": 10.0,
        "originalEnd": 400.0,
        "end": 100.0,
        "score": 80.0,
    }
    # The caller's own object must not be mutated by the trim.
    assert candidates[0]["end"] == 400.0
    assert "selection" not in candidates[0]["features"]


def test_degenerate_bounds_and_thresholds_never_crash():
    rows = [{"start": 0.0, "end": 30.0, "score": 50.0}]

    # A ceiling below the floor is contradictory: the floor wins rather than
    # emitting a clip shorter than the minimum it was asked to enforce.
    trimmed = select_candidates(rows, min_duration=20.0, max_duration=5.0)
    assert trimmed["report"]["maxDurationSeconds"] == 20.0
    assert trimmed["report"]["selectedCount"] == 1
    assert trimmed["selected"][0]["duration"] == 20.0

    for kwargs in (
        {"iou_threshold": float("nan")},
        {"iou_threshold": float("inf")},
        {"overlap_threshold": float("nan")},
        {"min_duration": float("nan")},
        {"max_duration": -5},
        {"max_duration": float("inf")},
        {"max_rejections": None},
    ):
        result = select_candidates(rows, **kwargs)
        assert result["report"]["selectedCount"] == 1, kwargs


def test_default_bounds_are_the_documented_conservative_ones():
    assert DEFAULT_MIN_CLIP_SECONDS == 3.0
    assert DEFAULT_MAX_CLIP_SECONDS == 90.0
    report = select_candidates([])["report"]
    assert report["minDurationSeconds"] == DEFAULT_MIN_CLIP_SECONDS
    assert report["maxDurationSeconds"] == DEFAULT_MAX_CLIP_SECONDS


def test_thresholds_are_clamped_into_the_unit_interval():
    assert select_candidates([], iou_threshold=5.0)["report"]["iouThreshold"] == 1.0
    assert select_candidates([], iou_threshold=-2.0)["report"]["iouThreshold"] == 0.0
    # A disabled containment check is reported as 0.0 on every return path.
    assert select_candidates(None, overlap_threshold=None)["report"]["overlapThreshold"] == 0.0
    assert select_candidates(None)["report"]["overlapThreshold"] == 0.8
    report = select_candidates([{"start": 0.0, "end": 10.0, "score": 1.0}])["report"]
    assert report["rejectedByReason"].keys() >= {
        "malformed", "invalid_interval", "too_short", "near_duplicate",
    }


def test_rejection_list_is_capped_but_counts_are_complete():
    candidates = [{"start": 0.0, "end": 10.0, "score": 1.0}] + [
        {"start": 1.0, "end": 9.0, "score": 1.0} for _ in range(10)
    ]

    result = select_candidates(candidates, max_rejections=2)

    assert len(result["rejected"]) == 2
    assert result["report"]["rejectedByReason"]["near_duplicate"] == 10
    assert result["report"]["rejectedCount"] == 10


# --------------------------------------------------------------------------------------
# Pipeline wiring
# --------------------------------------------------------------------------------------

def test_analyze_applies_duration_bounds_and_reports_the_selection(monkeypatch):
    from ai import main

    rows = [
        {"start": 0.0, "end": 1.0, "score": 99.0, "text": "A tiny fragment."},
        {"start": 100.0, "end": 300.0, "score": 95.0, "text": "A very long stretch."},
        {"start": 500.0, "end": 515.0, "score": 90.0, "text": "A normal length moment."},
    ]

    monkeypatch.setattr(main, "auth", lambda _secret: None)
    monkeypatch.setattr(main, "candidates", lambda *_a, **_k: [dict(row) for row in rows])
    monkeypatch.setattr(main, "optimize_candidates", lambda _segments, items: items)
    monkeypatch.setattr(main, "enrich_semantics", lambda items, _instruction: items)
    monkeypatch.setattr(main, "deduplicate", lambda items: items)
    monkeypatch.setattr(main, "enrich_candidates_with_context", lambda items, _segments: (items, {}))
    monkeypatch.setattr(main, "score_candidates", lambda items, *_a, **_k: items)
    monkeypatch.setattr(main, "diarize", lambda *_a: {"available": False, "segments": []})
    monkeypatch.setattr(main, "speaker_signals", lambda _segments: {"segments": []})
    monkeypatch.setattr(main, "apply_genre_profile", lambda items, *_a: items)
    monkeypatch.setattr(main, "apply_creator_preferences", lambda items, *_a: items)

    result = main.analyze(main.AnalyzeRequest(
        segments=[{"start": 0.0, "end": 1.0, "text": "A tiny fragment."}],
        genre="auto",
    ))

    delivered = result["candidates"]
    assert 0.0 not in [row["start"] for row in delivered]
    assert all(row["end"] - row["start"] <= DEFAULT_MAX_CLIP_SECONDS for row in delivered)

    report = result["selection"]
    assert report["rejectedByReason"]["too_short"] == 1
    assert report["trimmedCount"] == 1
    assert report["deliveredCount"] == len(delivered)


def test_bounded_analyze_keeps_the_diversified_order(monkeypatch, tmp_path):
    """Regression: the outer re-sort used to undo the recursive call's diversity pass."""
    from ai import main

    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    ranged = tmp_path / "range.mp4"
    ranged.write_bytes(b"x" * 2048)

    # Three distinct moments, all longer than the minimum clip duration. The first two
    # start 12 s apart, so the diversity pass defers the middle one.
    rows = [
        {"start": 1.0, "end": 11.0, "score": 95.0, "text": "First moment."},
        {"start": 13.0, "end": 23.0, "score": 90.0, "text": "Middle moment."},
        {"start": 25.0, "end": 29.0, "score": 85.0, "text": "Later moment."},
    ]

    monkeypatch.setattr(main, "auth", lambda _secret: None)
    monkeypatch.setattr(main, "ffprobe", lambda path: {"duration": 120 if path == str(source) else 30})
    monkeypatch.setattr(main, "extract_analysis_range", lambda _s, _a, _b, _out: str(ranged))
    monkeypatch.setattr(main, "analyze_media", lambda _path: {})
    monkeypatch.setattr(main, "candidates", lambda *_a, **_k: [dict(row) for row in rows])
    monkeypatch.setattr(main, "optimize_candidates", lambda _segments, items: items)
    monkeypatch.setattr(main, "enrich_semantics", lambda items, _instruction: items)
    monkeypatch.setattr(main, "deduplicate", lambda items: items)
    monkeypatch.setattr(main, "enrich_candidates_with_context", lambda items, _segments: (items, {}))
    monkeypatch.setattr(main, "score_candidates", lambda items, *_a, **_k: items)
    monkeypatch.setattr(main, "diarize", lambda *_a: {"available": False, "segments": []})
    monkeypatch.setattr(main, "speaker_signals", lambda _segments: {"segments": []})
    monkeypatch.setattr(main, "apply_genre_profile", lambda items, *_a: items)
    monkeypatch.setattr(main, "apply_creator_preferences", lambda items, *_a: items)

    result = main.analyze(main.AnalyzeRequest(
        segments=[{"start": 32, "end": 38, "text": "inside range"}],
        media_path=str(source),
        start_seconds=30,
        end_seconds=60,
    ))

    # Diversity ordering (95, 85, 90) survives; a plain score sort would return
    # (95, 90, 85) and pack the head with two adjacent windows.
    assert [row["score"] for row in result["candidates"]] == [95.0, 85.0, 90.0]
    assert result["selection"]["boundedRangeSeconds"] == [30.0, 60.0]
    assert result["selection"]["deliveredCount"] == 3


def test_longform_reports_a_beat_contained_inside_a_chapter(monkeypatch, tmp_path):
    from ai import main

    media = tmp_path / "source.mp4"
    media.write_bytes(b"source")

    chapter = {"start": 0.0, "end": 300.0, "score": 80.0, "text": "A full chapter."}
    beat = {"start": 120.0, "end": 140.0, "score": 60.0, "text": "A short beat inside it."}

    monkeypatch.setattr(main, "auth", lambda _secret: None)
    monkeypatch.setattr(main, "ffprobe", lambda _path: {"duration": 1000})
    monkeypatch.setattr(main, "stories", lambda _segments, limit: [dict(chapter), dict(beat)])
    monkeypatch.setattr(main, "score_candidates", lambda items, *_a, **_k: items)
    monkeypatch.setattr(main, "apply_genre_profile", lambda items, *_a: items)
    monkeypatch.setattr(main, "apply_creator_preferences", lambda items, *_a: items)

    result = main.longform(main.AnalyzeRequest(
        segments=[{"start": 0.0, "end": 300.0, "text": "A full chapter."}],
        media_path=str(media),
        genre="podcast",
    ))

    assert [story["start"] for story in result["stories"]] == [0.0]
    assert result["selection"]["rejectedByReason"]["near_duplicate"] == 1
    assert result["selection"]["deliveredCount"] == 1
