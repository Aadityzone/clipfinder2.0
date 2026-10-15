from ai import main
from ai.longform import package, stories


def test_story_candidates_keep_transcript_and_explainable_signals():
    segments = [
        {"start": 0, "end": 5, "text": "Wait, why did the experiment fail?"},
        {"start": 5, "end": 10, "text": "But then we found the missing step."},
    ]

    result = stories(segments)

    assert len(result) == 1
    assert result[0]["text"] == "Wait, why did the experiment fail? But then we found the missing step."
    assert result[0]["end"] == 10
    assert result[0]["features"]["story"]["hook"] > 0
    assert 0 <= result[0]["score"] <= 100


def test_longform_chapters_are_chronological_not_score_ordered():
    result = package(
        [{"start": 0, "end": 2, "text": "A transcript"}],
        [
            {"start": 90, "title": "Later but higher ranked"},
            {"start": 10, "title": "Earlier"},
        ],
    )

    assert [chapter["start"] for chapter in result["chapters"]] == [10, 90]


def test_longform_route_applies_llm_and_genre_ranking(monkeypatch):
    observed = {}

    monkeypatch.setattr(main, "auth", lambda _secret: None)
    monkeypatch.setattr(main, "stories", lambda _segments, limit=6: [{
        "start": 0, "end": 10, "score": 40, "title": "A story",
        "text": "A clutch changes the whole game.", "features": {},
    }])

    def rank(items, transcript, instruction, media_path=None):
        observed["transcript"] = transcript
        observed["instruction"] = instruction
        observed["media_path"] = media_path
        return items

    def genre(items, transcript, requested):
        observed["genre"] = requested
        return items

    monkeypatch.setattr(main, "score_candidates", rank)
    monkeypatch.setattr(main, "apply_genre_profile", genre)
    monkeypatch.setattr(main, "package", lambda _segments, _items: {
        "title": "Test", "description": "Test", "chapters": []
    })

    result = main.longform(main.AnalyzeRequest(
        segments=[{"start": 0, "end": 10, "text": "A clutch changes the whole game."}],
        instruction="Prioritize a clear payoff",
        genre="gaming",
        media_path="/tmp/source.mp4",
    ))

    assert result["title"] == "Test"
    assert observed["genre"] == "gaming"
    assert observed["instruction"] == "Prioritize a clear payoff"
    assert observed["media_path"] == "/tmp/source.mp4"
    assert "clutch" in observed["transcript"]

def test_story_windows_overlap_to_preserve_context_at_chunk_edges():
    segments = [
        {"start": index * 5, "end": (index + 1) * 5, "text": f"Segment {index} has useful context."}
        for index in range(12)
    ]

    result = stories(segments, limit=10)
    ranges = {(item["start"], item["end"]) for item in result}

    assert (0.0, 50.0) in ranges
    assert (25.0, 60.0) in ranges

