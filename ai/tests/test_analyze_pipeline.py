from fastapi.testclient import TestClient

from ai import main


client = TestClient(main.app)


def test_analyze_combines_transcript_and_media_event_candidates(monkeypatch):
    calls = []

    def transcript_candidates(segments, instruction, categories, media):
        calls.append("transcript_candidates")
        return [{"start": 1, "end": 8, "score": 60, "rationale": "Transcript moment", "features": {}}]

    def event_candidates(media, instruction, categories):
        calls.append("event_candidates")
        return [{"start": 20, "end": 32, "score": 55, "rationale": "Audio activity increased", "features": {"eventSource": "audio"}}]

    def passthrough(name):
        def apply(items, *args, **kwargs):
            calls.append(name)
            return items
        return apply

    monkeypatch.setattr(main, "candidates", transcript_candidates)
    monkeypatch.setattr(main, "enrich_semantics", passthrough("enrich_semantics"))
    monkeypatch.setattr(main, "optimize_candidates", lambda segments, items: items)
    monkeypatch.setattr(main, "generate_event_candidates", event_candidates)
    monkeypatch.setattr(main, "speaker_signals", lambda segments: {"segments": []})
    monkeypatch.setattr(main, "deduplicate", passthrough("deduplicate"))
    monkeypatch.setattr(main, "score_candidates", passthrough("score_candidates"))
    monkeypatch.setattr(main, "rank_candidates", passthrough("rank_candidates"))
    monkeypatch.setattr(main, "apply_creator_preferences", passthrough("apply_creator_preferences"))

    response = client.post(
        "/v1/analyze",
        json={
            "segments": [{"start": 1, "end": 8, "text": "That was unexpected"}],
            "instruction": "Find exciting moments",
            "categories": ["Funny"],
            "creator_preferences": {"high_energy": 0.5},
        },
    )

    assert response.status_code == 200, response.text
    result = response.json()["candidates"]
    assert len(result) == 2
    assert {candidate["rationale"] for candidate in result} == {
        "Transcript moment",
        "Audio activity increased",
    }
    event = next(candidate for candidate in result if candidate["start"] == 20)
    assert event["text"] == ""
    assert event["features"]["eventSource"] == "audio"
    assert calls.index("transcript_candidates") < calls.index("event_candidates")
    assert calls.index("deduplicate") < calls.index("score_candidates") < calls.index("rank_candidates")


def test_analyze_supports_event_only_candidates_without_transcript(monkeypatch):
    monkeypatch.setattr(main, "analyze_media", lambda media_path: {"audioWindows": []})
    monkeypatch.setattr(main, "candidates", lambda *args, **kwargs: [])
    monkeypatch.setattr(main, "enrich_semantics", lambda items, *_args: items)
    monkeypatch.setattr(main, "generate_event_candidates", lambda *_args: [
        {"start": 4, "end": 18, "score": 72, "rationale": "Visual activity changed", "features": {"eventSource": "visual"}}
    ])
    monkeypatch.setattr(main, "speaker_signals", lambda segments: {"segments": []})
    monkeypatch.setattr(main, "deduplicate", lambda items: items)
    monkeypatch.setattr(main, "score_candidates", lambda items, *_args: items)
    monkeypatch.setattr(main, "rank_candidates", lambda items: items)
    monkeypatch.setattr(main, "apply_creator_preferences", lambda items, *_args: items)

    response = client.post(
        "/v1/analyze",
        json={"segments": [], "media_path": "/fixture/video.mp4"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["candidates"] == [
        {
            "start": 4,
            "end": 18,
            "score": 72,
            "rationale": "Visual activity changed",
            "features": {
                "eventSource": "visual",
                "conversation": {
                    "questionCount": 0,
                    "styleTransitions": 0,
                    "secondPerson": 0,
                    "firstPerson": 0,
                },
            },
            "text": "",
        }
    ]
