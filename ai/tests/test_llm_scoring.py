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

def test_request_body_includes_labeled_visual_evidence():
    body = json.loads(llm._request_body(
        "vision-model",
        {"candidates": [{"i": 0, "text": "A surprise"}]},
        {0: "data:image/jpeg;base64,ZmFrZQ=="},
    ))
    content = body["input"][1]["content"]
    assert any(item.get("type") == "input_image" for item in content)
    assert any("candidate index 0" in item.get("text", "") for item in content)


def test_unsupported_multimodal_provider_falls_back_to_text(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(llm, "_candidate_frame_data_urls", lambda *_args, **_kwargs: {0: "data:image/jpeg;base64,ZmFrZQ=="})
    requests = []

    def fake_urlopen(request, **_kwargs):
        payload = json.loads(request.data)
        requests.append(payload)
        if len(requests) == 1:
            raise ValueError("provider does not support image input")
        return _FakeResponse({
            "output_text": json.dumps([{"i": 0, "score": 90, "rationale": "Strong moment"}])
        })

    monkeypatch.setattr(llm, "urlopen", fake_urlopen)
    candidates = [{
        "start": 1, "end": 8, "score": 60, "text": "A strong moment", "features": {}
    }]

    result = llm.score_candidates(candidates, "A strong moment", media_path="source.mp4")

    assert len(requests) == 2
    assert any(item.get("type") == "input_image" for item in requests[0]["input"][1]["content"])
    assert not isinstance(requests[1]["input"][1]["content"], list) or not any(
        item.get("type") == "input_image" for item in requests[1]["input"][1]["content"]
    )
    assert result[0]["features"]["llmScore"] == 90.0

def test_local_ollama_scores_candidates_without_cloud_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:3b")
    observed = {}

    def fake_urlopen(request, **_kwargs):
        observed["url"] = request.full_url
        observed["body"] = json.loads(request.data)
        return _FakeResponse({
            "message": {
                "content": json.dumps([{"i": 0, "score": 92, "rationale": "Clear payoff"}])
            }
        })

    monkeypatch.setattr(llm, "urlopen", fake_urlopen)
    candidates = [{
        "start": 4, "end": 18, "score": 50, "text": "The final reveal changes everything.",
        "features": {},
    }]

    result = llm.score_candidates(candidates, "The final reveal changes everything.")

    assert observed["url"] == "http://127.0.0.1:11434/api/chat"
    assert observed["body"]["model"] == "qwen2.5:3b"
    assert result[0]["features"]["llmProvider"] == "ollama"
    assert result[0]["features"]["llmScore"] == 92.0


def test_ranking_capabilities_reports_local_provider_without_secrets(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:3b")

    result = llm.ranking_capabilities()

    assert result == {
        "provider": "ollama",
        "configured": True,
        "model": "qwen2.5:3b",
        "visualRanking": False,
    }
    assert "apiKey" not in result


def test_ranking_capabilities_explicitly_reports_heuristic_fallback(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)

    result = llm.ranking_capabilities()

    assert result["provider"] == "heuristic"
    assert result["configured"] is False
