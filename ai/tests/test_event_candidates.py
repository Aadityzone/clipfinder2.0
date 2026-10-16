import math

from ai.services.event_candidates import generate_event_candidates


def test_generates_candidates_from_audio_peaks_without_transcript():
    media = {
        "audio": {"durationS": 120},
        "audioWindows": [
            {"start": 0, "end": 5, "energy": 0.12},
            {"start": 20, "end": 25, "energy": 0.25},
            {"start": 45, "end": 50, "energy": 0.91, "peakDb": -2.0},
            {"start": 50, "end": 55, "energy": 0.84, "peakDb": -3.0},
            {"start": 90, "end": 95, "energy": 0.18},
        ],
    }

    result = generate_event_candidates(media)

    assert result
    assert all(item["features"]["candidateSource"] == "media_events" for item in result)
    assert any("audio_energy" in item["features"]["eventTypes"] for item in result)
    assert all(0 <= item["start"] < item["end"] <= 120 for item in result)


def test_generates_visual_and_on_screen_candidates_for_low_speech_gameplay():
    media = {
        "durationS": 90,
        "visual": {"samples": [
            {"time": 30, "visualChange": 0.9, "motion": 0.8, "centerDetail": 0.5},
        ]},
        "onScreen": {"samples": [
            {"time": 31, "gameplayLike": True, "actionLabels": ["combat"], "ocrText": "VICTORY"},
        ]},
    }

    result = generate_event_candidates(media)

    assert result
    candidate = next(item for item in result if "on_screen_event" in item["features"]["eventTypes"])
    assert "visual_change" in candidate["features"]["eventTypes"]
    assert candidate["features"]["visualChange"] == 0.9
    assert candidate["features"]["motion"] == 0.8
    assert candidate["features"]["gameplayLikeRatio"] == 1.0
    assert candidate["features"]["onScreenActionLabels"] == ["combat"]
    assert candidate["features"]["onScreenText"] == "VICTORY"
    assert all(item["text"] == "" for item in result)


def test_missing_or_invalid_media_data_degrades_to_no_candidates():
    assert generate_event_candidates(None) == []
    assert generate_event_candidates({"durationS": math.nan, "audioWindows": []}) == []


def test_specific_semantic_category_does_not_get_fabricated_from_visual_signals():
    media = {
        "durationS": 30,
        "audioWindows": [{"start": 10, "end": 15, "energy": 0.95}],
    }

    assert generate_event_candidates(media, categories=["funny"]) == []
    assert generate_event_candidates(media, categories=["ai_detect"])


def test_event_windows_are_bounded_for_short_media():
    media = {
        "durationS": 4,
        "audioWindows": [{"start": 0, "end": 4, "energy": 0.99}],
    }

    result = generate_event_candidates(media)

    assert result
    assert result[0]["start"] == 0
    assert result[0]["end"] == 4


def test_analyze_route_returns_event_candidates_without_transcript(monkeypatch):
    from ai import main

    media = {
        "audio": {"durationS": 60},
        "audioWindows": [
            {"start": 20, "end": 25, "energy": 0.95, "peakDb": -1.5},
        ],
    }
    monkeypatch.setattr(main, "analyze_media", lambda _path: media)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    response = main.analyze(main.AnalyzeRequest(
        segments=[],
        media_path="/synthetic/fixture.mp4",
        categories=["ai_detect"],
    ))

    assert response["candidates"]
    assert any(
        item.get("features", {}).get("candidateSource") == "media_events"
        for item in response["candidates"]
    )
    assert all(0 <= item["start"] < item["end"] <= 60 for item in response["candidates"])



def test_audio_event_window_is_centered_on_energy_window_midpoint():
    media = {
        "durationS": 120,
        "audioWindows": [
            {"start": 40, "end": 50, "energy": 0.95, "peakDb": -4.0},
        ],
    }

    result = generate_event_candidates(media)

    assert len(result) == 1
    candidate = result[0]
    midpoint = (candidate["start"] + candidate["end"]) / 2
    assert abs(midpoint - 45) < 0.01
    assert candidate["features"]["audioPeakDb"] == -4.0
