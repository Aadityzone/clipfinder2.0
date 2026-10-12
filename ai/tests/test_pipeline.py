from ai.highlights import candidates
from ai.services.dedup import deduplicate
from ai.services import llm

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


def test_llm_missing_key_is_observable_without_changing_score(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    item = {"start": 0, "end": 5, "score": 60, "features": {}}

    result = llm.score_candidates([item], "hello")

    assert result[0]["score"] == 60
    assert result[0]["features"]["llmScoring"] == {
        "status": "skipped", "reason": "missing_api_key"
    }


def test_llm_applies_only_valid_candidate_indexes_and_scores(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False
        def read(self):
            return (b'{"output_text":"[{\\"i\\":0,\\"score\\":100,\\"rationale\\":\\"valid\\"},'
                    b'{\\"i\\":1,\\"score\\":\\"bad\\"},{\\"i\\":99,\\"score\\":90}]"}')
    monkeypatch.setattr(llm, "urlopen", lambda *_args, **_kwargs: Response())
    items = [
        {"start": 0, "end": 5, "score": 60, "features": {}},
        {"start": 5, "end": 10, "score": 40, "features": {}},
    ]

    result = llm.score_candidates(items, "hello")

    assert result[0]["score"] == 78
    assert result[0]["rationale"] == "valid"
    assert result[0]["features"]["llmScore"] == 100
    assert result[0]["features"]["llmScoring"] == {"status": "applied"}
    assert result[1]["score"] == 40
    assert result[1]["features"]["llmScoring"] == {
        "status": "partial", "reason": "invalid_model_output"
    }


def test_llm_request_failure_and_malformed_response_are_observable(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    item = {"start": 0, "end": 5, "score": 60, "features": {}}
    monkeypatch.setattr(llm, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError()))

    result = llm.score_candidates([item], "hello")

    assert result[0]["score"] == 60
    assert result[0]["features"]["llmScoring"] == {
        "status": "failed", "reason": "request_or_response_error"
    }

    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False
        def read(self):
            return b'{"output_text":"not json"}'
    monkeypatch.setattr(llm, "urlopen", lambda *_args, **_kwargs: Response())
    result = llm.score_candidates([item], "hello")
    assert result[0]["features"]["llmScoring"] == {
        "status": "failed", "reason": "request_or_response_error"
    }


def test_llm_request_construction_failure_is_observable(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    item = {"start": 0, "end": 5, "score": 60, "features": {}}
    monkeypatch.setattr(llm, "Request", lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError()))

    result = llm.score_candidates([item], "hello")

    assert result[0]["score"] == 60
    assert result[0]["features"]["llmScoring"] == {
        "status": "failed", "reason": "request_or_response_error"
    }


def test_llm_duplicate_indexes_keep_first_valid_score_and_reject_later_duplicate(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False
        def read(self):
            return (b'{"output_text":"[{\\"i\\":0,\\"score\\":80},'
                    b'{\\"i\\":0,\\"score\\":10},{\\"i\\":1,\\"score\\":1e999}]"}')
    monkeypatch.setattr(llm, "urlopen", lambda *_args, **_kwargs: Response())
    items = [
        {"start": 0, "end": 5, "score": 60, "features": {}},
        {"start": 5, "end": 10, "score": 40, "features": {}},
    ]

    result = llm.score_candidates(items, "hello")

    assert result[0]["score"] == 69
    assert result[0]["features"]["llmScoring"] == {"status": "applied"}
    assert result[1]["score"] == 40
    assert result[1]["features"]["llmScoring"] == {
        "status": "partial", "reason": "invalid_model_output"
    }
    assert llm._valid_score(10 ** 400) is None
