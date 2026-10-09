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
