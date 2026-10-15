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
