from ai.services.genre_intelligence import (
    apply_genre_profile,
    infer_genre,
    normalize_genre,
)


def test_normalize_common_genre_aliases():
    assert normalize_genre("IRL stream") == "irl_stream"
    assert normalize_genre("educational") == "knowledge"
    assert normalize_genre("movies") == "movies_tv"
    assert normalize_genre("unknown genre") == "auto"


def test_infer_genre_requires_multiple_cues():
    assert infer_genre("Hello everyone, welcome back.") [0] == "general"
    genre, scores = infer_genre(
        "This GPU benchmark compares CPU performance. The graphics card review "
        "also measures latency and memory."
    )
    assert genre == "tech"
    assert scores["tech"] >= 2


def test_selected_genre_adds_explainable_bonus_to_matching_candidate():
    candidates = [
        {"text": "That clutch was insane, clean headshot and victory!", "score": 50, "features": {}},
        {"text": "Today we are discussing a simple recipe for lunch.", "score": 50, "features": {}},
    ]
    result = apply_genre_profile(candidates, "A gaming stream with a clutch and headshot.", "gaming")
    assert result[0]["score"] > 50
    assert result[0]["features"]["genreProfile"]["active"] == "gaming"
    assert result[0]["features"]["genreProfile"]["cueMatches"] >= 2
    assert result[1]["score"] == 50


def test_auto_mode_records_detected_genre_and_abstains_on_weak_evidence():
    candidates = [{"text": "This GPU benchmark is a graphics card review.", "score": 40, "features": {}}]
    result = apply_genre_profile(candidates, "We compare GPU performance and graphics card benchmarks.", "auto")
    assert result[0]["features"]["genreProfile"]["detected"] == "tech"
    unknown = [{"text": "Hello there.", "score": 40, "features": {}}]
    result = apply_genre_profile(unknown, "Hello there.", "auto")
    assert result[0]["features"]["genreProfile"]["active"] == "general"



def test_genre_cues_do_not_match_inside_unrelated_words():
    # "skill" must not trigger the gaming cue "kill".
    genre, scores = infer_genre("The developer explains a useful skill for beginners.")
    assert scores["gaming"] == 0
    assert genre == "general"


def test_auto_genre_detection_abstains_when_top_profiles_tie():
    genre, scores = infer_genre(
        "The episode includes an interview and a game review with a final round."
    )
    # A tie should not be resolved by dictionary ordering.
    top = max(scores.values())
    leaders = [name for name, score in scores.items() if score == top]
    if len(leaders) > 1:
        assert genre == "general"



def test_genre_profiles_use_available_modality_features():
    podcast = [{
        "text": "I disagree with your point, and here is why.",
        "score": 50,
        "features": {"speakers": {"turnCount": 4}, "faceHits": 2},
    }]
    apply_genre_profile(podcast, "This is an interview and conversation.", "podcast")
    assert podcast[0]["score"] > 50

    educational = [{
        "text": "The process is explained step by step.",
        "score": 50,
        "features": {"story": {"completeness": 0.9, "payoff": 0.8}},
    }]
    apply_genre_profile(educational, "Here is how the process works because of this principle.", "knowledge")
    assert educational[0]["score"] > 50

    gaming = [{
        "text": "The round ends with victory.",
        "score": 50,
        "features": {"onScreenActionLabels": ["victory"], "gameplayLikeRatio": 0.8},
    }]
    apply_genre_profile(gaming, "The final round ended in victory.", "gaming")
    assert gaming[0]["score"] > 50

def test_every_explicit_genre_profile_uses_its_own_transcript_evidence():
    examples = {
        "gaming": "The final round ended in a clutch victory.",
        "irl_stream": "That prank reaction was wild, bro.",
        "movies_tv": "The plot twist reveals the villain in the final scene.",
        "anime": "The domain expansion transformation reaches its final form.",
        "tech": "This GPU benchmark measures processor performance and latency.",
        "knowledge": "Here is how the principle works because of the evidence.",
        "facts": "Did you know scientists discovered a surprising record?",
        "podcast": "I disagree with that point; let me explain my experience.",
    }

    for genre, text in examples.items():
        candidate = [{"text": text, "score": 50, "features": {}}]
        result = apply_genre_profile(candidate, text, genre)
        profile = result[0]["features"]["genreProfile"]
        assert profile["active"] == genre
        assert profile["cueMatches"] > 0
        assert result[0]["score"] > 50

