from ai.services.diarization import diarization_status, _speaker_at


def test_speaker_overlap_assignment():
    intervals = [(0.0, 3.0, "SPEAKER_00"), (3.0, 7.0, "SPEAKER_01")]
    assert _speaker_at(intervals, 0.5, 2.0) == "SPEAKER_00"
    assert _speaker_at(intervals, 4.0, 5.0) == "SPEAKER_01"


def test_diarization_is_explicitly_optional():
    status = diarization_status()
    assert "available" in status
    assert "model" in status
