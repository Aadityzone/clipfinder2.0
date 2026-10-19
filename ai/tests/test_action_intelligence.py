from ai.services.action_intelligence import _classify_ocr


def test_ocr_labels_gameplay_victory_and_combat():
    labels = _classify_ocr("VICTORY! HEADSHOT +100 POINTS")
    assert "victory" in labels
    assert "combat" in labels
    assert "score_change" in labels


def test_ocr_labels_stream_overlay():
    labels = _classify_ocr("New subscriber followed")
    assert "stream_overlay" in labels


def test_unknown_ocr_text_does_not_invent_action():
    assert _classify_ocr("health ammo inventory") == []

def test_ocr_action_terms_match_whole_words_not_substrings():
    assert _classify_ocr("window skill windowsill") == []
    labels = _classify_ocr("WIN! The enemy was eliminated.")
    assert "victory" in labels
    assert "combat" in labels


def test_ocr_phrase_matching_ignores_case_and_extra_whitespace():
    labels = _classify_ocr("GAME   OVER — YOU DIED")
    assert "failure" in labels


def test_ocr_multi_word_phrase_matches_with_runs_of_whitespace_alone():
    # Regression: the phrase itself must match when the only whitespace is
    # irregular. Previously "GAME   OVER" was missed because the phrase was not
    # whitespace-normalized, and only the single-spaced "you died" matched.
    assert _classify_ocr("GAME   OVER") == ["failure"]
    assert _classify_ocr("game\tover") == ["failure"]
    assert _classify_ocr("try\nagain") == ["failure"]


def test_ocr_action_terms_do_not_match_across_word_boundaries():
    # Normalizing whitespace must not turn separate tokens into a false phrase.
    assert _classify_ocr("the game is over there") == []
    assert _classify_ocr("you dieded") == []

