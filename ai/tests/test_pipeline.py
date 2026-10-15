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
        {"start": 0, "end": 10, "text": "The final reveal changes everything in the story.", "features": {}},
        {"start": 65, "end": 80, "text": "", "category": "ai_detect", "features": {"eventKind": "visual_change"}},
    ])

    assert result[0]["title"] == "The final reveal changes everything…"
    assert result[0]["features"]["titleSource"] == "transcript_extract"
    assert result[1]["title"] == "Visual Change at 01:05"
    assert result[1]["features"]["titleSource"] == "visual_timestamp"

