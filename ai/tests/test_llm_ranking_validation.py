import json
import math

import pytest

from ai.services.llm import _parse_rankings


def test_parse_rankings_accepts_valid_integer_and_digit_string_indexes():
    result = _parse_rankings(json.dumps([
        {"i": 0, "score": 90, "rationale": "Strong payoff", "title": "Payoff"},
        {"i": "2", "score": 75, "rationale": "Good setup"},
    ]))

    assert result[0]["score"] == 90
    assert result[0]["title"] == "Payoff"
    assert result[2]["score"] == 75


@pytest.mark.parametrize("bad_index", [True, False, 1.5, -0.5, "1.5", "abc", None, []])
def test_parse_rankings_rejects_non_integer_indexes(bad_index):
    result = _parse_rankings(json.dumps([{"i": bad_index, "score": 80}]))
    assert result == {}


@pytest.mark.parametrize("bad_score", [float("nan"), float("inf"), float("-inf"), -1, 101, "not-a-score", None])
def test_parse_rankings_rejects_non_finite_or_out_of_range_scores(bad_score):
    result = _parse_rankings(json.dumps([{"i": 0, "score": bad_score}]))
    assert result == {}


def test_duplicate_index_keeps_highest_valid_score():
    result = _parse_rankings(json.dumps([
        {"i": 1, "score": 88, "rationale": "Best"},
        {"i": 1, "score": 24, "rationale": "Duplicate downgrade"},
        {"i": 1, "score": 88, "rationale": "Equal duplicate"},
    ]))

    assert result[1]["score"] == 88
    assert result[1]["rationale"] == "Best"


def test_parse_rankings_still_accepts_fenced_json():
    result = _parse_rankings(' ```json\n[{"i": 3, "score": 64}]\n``` ')
    assert result == {3: {"score": 64.0, "rationale": ""}}
