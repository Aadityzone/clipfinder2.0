import json

from ai.services import llm


def test_response_text_reads_raw_responses_api_output():
    payload = {
        "output": [{
            "type": "message",
            "content": [{"type": "output_text", "text": '[{"i": 0, "score": 91, "rationale": "Strong payoff"}]'}],
        }]
    }
    assert llm._response_text(payload) == '[{"i": 0, "score": 91, "rationale": "Strong payoff"}]'


def test_response_text_prefers_sdk_output_text():
    assert llm._response_text({
        "output_text": '[{"i": 0, "score": 80}]',
        "output": [{"content": [{"type": "output_text", "text": "wrong"}]}],
    }) == '[{"i": 0, "score": 80}]'


def test_parse_rankings_accepts_fenced_json_and_ignores_bad_indexes():
    raw = """```json
    [{"i": 0, "score": 90, "rationale": "Great"}, {"i": -1, "score": 99},
     {"i": 2, "score": 101}, {"i": "bad", "score": 50}, "invalid"]
    ```"""
    assert llm._parse_rankings(raw) == {
        0: {"score": 90.0, "rationale": "Great"}
    }


def test_score_candidates_uses_raw_responses_payload(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(llm, "urlopen", lambda *args, **kwargs: _FakeResponse({
        "output": [{
            "content": [{
                "type": "output_text",
                "text": json.dumps([{"i": 0, "score": 100, "rationale": "Excellent payoff"}]),
            }]
        }]
    }))

    candidates = [{"start": 1, "end": 8, "score": 60, "text": "A big surprise", "features": {}}]
    result = llm.score_candidates(candidates, "A big surprise")

    assert result[0]["score"] == 78.0
    assert result[0]["rationale"] == "Excellent payoff"
    assert result[0]["features"]["llmScore"] == 100.0


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()
