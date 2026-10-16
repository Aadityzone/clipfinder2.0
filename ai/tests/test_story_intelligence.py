from ai.services.story_intelligence import analyze_story, story_score, find_boundaries

def test_story_signals_reward_payoff():
    weak = analyze_story("This is some information about a topic.", 25)
    strong = analyze_story("Wait, why did it fail? But then we realized the real reason, and that's why we won.", 25)
    assert story_score(strong) > story_score(weak)
    assert strong.payoff > weak.payoff
    assert strong.hook > weak.hook

def test_boundaries_include_context():
    segments = [
        {"start": 0, "end": 4, "text": "Earlier setup."},
        {"start": 4, "end": 8, "text": "We had a problem."},
        {"start": 8, "end": 12, "text": "Wait, why did this happen?"},
        {"start": 12, "end": 18, "text": "But then we realized the answer."},
        {"start": 18, "end": 24, "text": "That's why we won."},
    ]
    start, end = find_boundaries(segments, 2, min_duration=12, max_duration=75)
    assert start <= 4
    assert end >= 18

def test_story_cues_do_not_match_inside_unrelated_words():
    signals = analyze_story("The sofa is beside the sofa, and the software is stable.", 20)
    assert signals.hook == 0
    assert signals.tension == 0
    assert signals.payoff < 0.5


def test_story_conversation_signal_handles_capitalization_and_punctuation():
    signals = analyze_story("YOU, I think we should try again.", 20)
    assert signals.conversational > 0


def test_phrase_matching_normalizes_repeated_whitespace():
    from ai.services.story_intelligence import _contains_phrase

    assert _contains_phrase("Wait    what happened?", "wait what")
    assert _contains_phrase("The   thing is", "the thing")


def test_story_boundaries_skip_malformed_segments():
    segments = [
        None,
        {"start": "bad", "end": 2, "text": "bad"},
        {"start": 3, "end": 6, "text": "valid setup"},
        {"start": 6, "end": 10, "text": "valid payoff"},
    ]
    start, end = find_boundaries(segments, 1, min_duration=2, max_duration=20)
    assert start >= 0
    assert end > start


def test_story_optimizer_ignores_malformed_candidates_and_segments():
    from ai.services.story_intelligence import optimize_candidates

    assert optimize_candidates([], [{"start": 1, "end": 4, "score": 80}]) == []
    result = optimize_candidates(
        [None, {"start": 0, "end": 4, "text": "A complete thought.", "words": []}],
        [None, {"start": 0, "end": 4, "score": 60, "features": None}],
    )
    assert len(result) == 1
    assert isinstance(result[0]["features"]["story"], dict)
