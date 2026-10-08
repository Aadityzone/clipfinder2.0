from ai.highlights import candidates
from ai.services.dedup import deduplicate

def test_candidates_keep_text_and_context_features():
    segments = [
        {"start": 10, "end": 14, "text": "Wait, you are telling me this actually happened? No way!"},
        {"start": 15, "end": 20, "text": "And then everyone started laughing because it was completely unexpected."},
    ]
    result = candidates(segments, "find surprising funny moments", ["ai_detect"], {
        "audio": {},
        "scenes": {"sceneChanges": [13.0]},
        "vision": {"faces": [{"time": 12, "x": .7}]},
    })
    assert result
    assert result[0]["text"]
    assert result[0]["features"]["faceHits"] == 1
    assert result[0]["features"]["sceneHits"] == 1

def test_dedup_prefers_highest_score():
    items = [
        {"start": 0, "end": 10, "score": 60},
        {"start": 1, "end": 9, "score": 90},
        {"start": 30, "end": 40, "score": 50},
    ]
    result = deduplicate(items, threshold=.55)
    assert [x["score"] for x in result] == [90, 50]
