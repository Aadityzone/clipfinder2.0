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
