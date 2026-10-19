from ai.highlights import candidates
from ai.services.dedup import deduplicate

def test_custom_instruction_changes_candidate_score():
    segments=[{"start":0,"end":12,"text":"This is a surprising story about the biggest mistake I ever made!"}]
    base=candidates(segments)
    targeted=candidates(segments,"find surprising stories",["AI Detect"])
    assert base and targeted
    assert targeted[0]["score"]>=base[0]["score"]

def test_selected_category_filters_candidates():
    segments=[{"start":0,"end":10,"text":"That was hilarious, everyone started to laugh!"}]
    result=candidates(segments,None,["Funny"])
    assert result
    assert result[0]["category"]=="funny"

def test_dedup_keeps_highest_scoring_overlap():
    items=[{"start":0,"end":10,"score":90},{"start":1,"end":9,"score":70},{"start":20,"end":30,"score":60}]
    result=deduplicate(items)
    assert len(result)==2
    assert result[0]["score"]==90


def test_analyze_forwards_explicit_genre_to_ranking(monkeypatch):
    from ai import main

    observed = {}
    candidate = {
        "start": 1.0,
        "end": 8.0,
        "score": 50.0,
        "text": "A surprising gaming clutch!",
        "category": "ai_detect",
        "rationale": "test evidence",
        "features": {},
    }

    monkeypatch.setattr(main, "auth", lambda _secret: None)
    monkeypatch.setattr(main, "candidates", lambda *args, **kwargs: [dict(candidate)])
    monkeypatch.setattr(main, "optimize_candidates", lambda _segments, rows: rows)
    monkeypatch.setattr(main, "enrich_semantics", lambda rows, _instruction: rows)
    monkeypatch.setattr(main, "deduplicate", lambda rows: rows)
    monkeypatch.setattr(main, "score_candidates", lambda rows, _transcript, _instruction, **_kwargs: rows)
    def record_genre(rows, _transcript, genre):
        observed["genre"] = genre
        return rows

    monkeypatch.setattr(main, "apply_genre_profile", record_genre)
    monkeypatch.setattr(main, "apply_creator_preferences", lambda rows, _preferences: rows)

    result = main.analyze(main.AnalyzeRequest(
        segments=[{"start": 1.0, "end": 8.0, "text": "A surprising gaming clutch!"}],
        genre="gaming",
    ))

    assert observed["genre"] == "gaming"
    assert result["candidates"]

def test_highlight_cues_do_not_match_inside_unrelated_words():
    from ai.highlights import _contains_cue

    assert not _contains_cue("the window is open", "win")
    assert not _contains_cue("a useful skill for beginners", "kill")
    assert _contains_cue("That was a huge win!", "win")
    assert _contains_cue("I can't believe it", "can't believe")

def test_candidates_receive_grounded_title_fallbacks_without_an_llm():
    from ai.main import _ensure_candidate_titles

    result = _ensure_candidate_titles([
        {"start": 0, "end": 10, "text": "The final reveal changes everything in the story tonight.", "features": {}},
        {"start": 65, "end": 80, "text": "", "category": "ai_detect", "features": {"eventKind": "visual_change"}},
    ])

    assert result[0]["title"] == "The final reveal changes everything in the story…"
    assert result[0]["features"]["titleSource"] == "transcript_extract"
    assert result[1]["title"] == "Visual Change at 01:05"
    assert result[1]["features"]["titleSource"] == "visual_timestamp"

def test_longform_rejects_missing_media_path(monkeypatch, tmp_path):
    import pytest
    from fastapi import HTTPException
    from ai import main

    monkeypatch.setattr(main, "auth", lambda _secret: None)
    request = main.AnalyzeRequest(
        segments=[{"start": 0, "end": 5, "text": "A complete story."}],
        media_path=str(tmp_path / "missing.mp4"),
    )

    with pytest.raises(HTTPException) as error:
        main.longform(request)

    assert error.value.status_code == 404


def test_longform_clips_ranked_stories_to_media_duration(monkeypatch, tmp_path):
    from ai import main

    media = tmp_path / "source.mp4"
    media.write_bytes(b"test")
    candidate = {
        "start": 80,
        "end": 120,
        "score": 140,
        "text": "The story reaches its final payoff.",
        "title": "The Final Payoff",
        "rationale": "A grounded ending.",
        "features": {"story": {"payoff": 0.9}},
    }
    monkeypatch.setattr(main, "auth", lambda _secret: None)
    monkeypatch.setattr(main, "ffprobe", lambda _path: {"duration": 100})
    monkeypatch.setattr(main, "stories", lambda _segments, limit: [dict(candidate)])
    monkeypatch.setattr(
        main, "score_candidates",
        lambda rows, _transcript, _instruction, **_kwargs: rows,
    )
    monkeypatch.setattr(main, "apply_genre_profile", lambda rows, _transcript, _genre: rows)
    monkeypatch.setattr(main, "apply_creator_preferences", lambda rows, _preferences: rows)
    monkeypatch.setattr(main, "deduplicate", lambda rows, threshold: rows)

    result = main.longform(main.AnalyzeRequest(
        segments=[{"start": 0, "end": 100, "text": "The story reaches its final payoff."}],
        media_path=str(media),
        genre="podcast",
        creator_preferences={},
    ))

    assert len(result["stories"]) == 1
    assert result["stories"][0]["start"] == 80
    assert result["stories"][0]["end"] == 100
    assert result["stories"][0]["score"] == 100
    assert result["chapters"][0]["start"] == 80.0


def test_bounded_analyze_shifts_candidates_back_to_source_timestamps(monkeypatch, tmp_path):
    from ai import main

    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    ranged = tmp_path / "range.mp4"
    ranged.write_bytes(b"x" * 2048)
    monkeypatch.setattr(main, "auth", lambda _secret: None)
    monkeypatch.setattr(main, "ffprobe", lambda path: {"duration": 120 if path == str(source) else 30})
    monkeypatch.setattr(main, "extract_analysis_range", lambda _source, _start, _end, _out: str(ranged))
    monkeypatch.setattr(main, "analyze_media", lambda _path: {})
    monkeypatch.setattr(main, "candidates", lambda *_args, **_kwargs: [
        {"start": 1.0, "end": 5.0, "score": 80.0, "text": "A strong moment", "features": {}}
    ])
    monkeypatch.setattr(main, "optimize_candidates", lambda _segments, rows: rows)
    monkeypatch.setattr(main, "enrich_semantics", lambda rows, _instruction: rows)
    monkeypatch.setattr(main, "validate_candidates", lambda rows, _duration: rows)
    monkeypatch.setattr(main, "diarize", lambda *_args: {"available": False, "segments": []})
    monkeypatch.setattr(main, "speaker_signals", lambda _segments: {"segments": []})
    monkeypatch.setattr(main, "deduplicate", lambda rows: rows)
    monkeypatch.setattr(main, "score_candidates", lambda rows, *_args, **_kwargs: rows)
    monkeypatch.setattr(main, "apply_genre_profile", lambda rows, *_args: rows)
    monkeypatch.setattr(main, "apply_creator_preferences", lambda rows, *_args: rows)

    result = main.analyze(main.AnalyzeRequest(
        segments=[{"start": 32, "end": 38, "text": "inside range"}],
        media_path=str(source),
        start_seconds=30,
        end_seconds=60,
    ))

    assert result["candidates"][0]["start"] == 31.0
    assert result["candidates"][0]["end"] == 35.0


def test_highlight_cue_matching_normalizes_repeated_whitespace():
    from ai.highlights import _contains_cue

    assert _contains_cue("I cannot believe that happened", "cannot believe")
    assert _contains_cue("I cannot" + "\t" + "believe that happened", "cannot believe")


def test_dedup_discards_invalid_intervals_and_non_finite_scores():
    items = [
        {"start": 0, "end": 10, "score": 90},
        {"start": float("nan"), "end": 12, "score": 100},
        {"start": 11, "end": 11, "score": 80},
        {"start": 20, "end": 30, "score": float("nan")},
        {"start": 40, "end": 50, "score": 60},
    ]
    result = deduplicate(items)
    assert [(row["start"], row["end"]) for row in result] == [(0, 10), (40, 50), (20, 30)]
    assert result[2]["score"] == 0.0


def test_dedup_clamps_invalid_threshold_to_safe_range():
    items = [
        {"start": 0, "end": 10, "score": 90},
        {"start": 1, "end": 9, "score": 80},
    ]
    assert len(deduplicate(items, threshold=float("nan"))) == 1


def test_analyze_promotes_temporal_spread_across_the_source(monkeypatch):
    """Regression: enforce_temporal_diversity must actually run during /v1/analyze.

    Previously it was imported but never called, so the strongest candidates could
    all sit in one narrow window of a long video.
    """
    from ai import main

    rows = [
        {"start": 0.0, "end": 12.0, "score": 90.0, "text": "First strong moment with a full sentence.", "features": {}, "category": "ai_detect"},
        {"start": 20.0, "end": 32.0, "score": 89.0, "text": "Second strong moment with a full sentence.", "features": {}, "category": "ai_detect"},
        {"start": 40.0, "end": 52.0, "score": 88.0, "text": "Third strong moment with a full sentence.", "features": {}, "category": "ai_detect"},
        {"start": 600.0, "end": 612.0, "score": 50.0, "text": "Distant moment with a full sentence.", "features": {}, "category": "ai_detect"},
    ]

    monkeypatch.setattr(main, "auth", lambda _secret: None)
    monkeypatch.setattr(main, "candidates", lambda *args, **kwargs: [dict(row) for row in rows])
    monkeypatch.setattr(main, "optimize_candidates", lambda _segments, items: items)
    monkeypatch.setattr(main, "multimodal_event_candidates", lambda *args, **kwargs: [])
    monkeypatch.setattr(main, "enrich_semantics", lambda items, _instruction: items)
    monkeypatch.setattr(main, "analyze_media", lambda _path: {})
    monkeypatch.setattr(main, "deduplicate", lambda items: items)
    monkeypatch.setattr(main, "enrich_candidates_with_context", lambda items, _segments: (items, {}))
    monkeypatch.setattr(main, "score_candidates", lambda items, *args, **kwargs: items)
    monkeypatch.setattr(main, "diarize", lambda *args: {"available": False, "segments": []})
    monkeypatch.setattr(main, "speaker_signals", lambda _segments: {"segments": []})
    monkeypatch.setattr(main, "apply_genre_profile", lambda items, *args, **kwargs: items)
    monkeypatch.setattr(main, "apply_creator_preferences", lambda items, *args: items)

    result = main.analyze(main.AnalyzeRequest(
        segments=[{"start": 0.0, "end": 12.0, "text": "First strong moment with a full sentence."}],
        genre="auto",
    ))

    # The distant, lower-scoring candidate is promoted ahead of the third
    # clustered candidate instead of everything being grouped by raw score.
    assert [c["score"] for c in result["candidates"]] == [90.0, 89.0, 50.0, 88.0]
    assert len(result["candidates"]) == 4
