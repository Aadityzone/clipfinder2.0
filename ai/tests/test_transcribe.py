import importlib
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

transcription = importlib.import_module("ai.transcribe")


def test_model_initializes_only_once_under_concurrent_calls(monkeypatch):
    monkeypatch.setattr(transcription, "_model", None)
    count = 0
    count_lock = threading.Lock()

    class FakeWhisperModel:
        def __init__(self, *args, **kwargs):
            nonlocal count
            time.sleep(0.02)
            with count_lock:
                count += 1

    monkeypatch.setattr(transcription, "WhisperModel", FakeWhisperModel)
    with ThreadPoolExecutor(max_workers=8) as pool:
        models = list(pool.map(lambda _index: transcription.model(), range(8)))

    assert count == 1
    assert all(instance is models[0] for instance in models)


def test_transcribe_preserves_segment_and_word_timestamps(monkeypatch):
    word = SimpleNamespace(start=1.2, end=1.6, word=" hello", probability=0.97)
    segment = SimpleNamespace(start=1.0, end=2.0, text=" hello world ", words=[word])
    fake_model = SimpleNamespace(
        transcribe=lambda path, **kwargs: (
            iter([segment]),
            SimpleNamespace(language="en", duration=12.5),
        )
    )
    monkeypatch.setattr(transcription, "_model", fake_model)

    result = transcription.transcribe("source.mp4", language="en")

    assert result["language"] == "en"
    assert result["text"] == "hello world"
    assert result["duration"] == 12.5
    assert result["segments"][0]["start"] == 1.0
    assert result["segments"][0]["words"][0]["confidence"] == 0.97


def test_transcription_range_validates_one_hour_limit():
    from ai.services.transcription_range import validate_transcription_range

    assert validate_transcription_range(120, 3720, 5000) == (120.0, 3720.0)
    try:
        validate_transcription_range(0, 3600.01, 4000)
    except ValueError as exc:
        assert "one hour" in str(exc)
    else:
        raise AssertionError("ranges longer than one hour must be rejected")


def test_transcription_range_restores_absolute_word_timestamps(monkeypatch):
    from ai.services import transcription_range as ranged

    monkeypatch.setattr(ranged.subprocess, "run", lambda *args, **kwargs: None)
    monkeypatch.setattr(ranged, "transcribe", lambda path, language: {
        "language": "en", "text": "hello", "duration": 2.0,
        "segments": [{"start": 0.5, "end": 1.5, "text": "hello",
                      "words": [{"start": 0.75, "end": 1.0, "word": "hello"}]}],
    })
    result = ranged.transcribe_range("source.mp4", 600, 602, 1000, "en")

    assert result["sourceStartS"] == 600
    assert result["sourceEndS"] == 602
    assert result["segments"][0]["start"] == 600.5
    assert result["segments"][0]["words"][0]["end"] == 601.0


def test_transcribe_timeout_raises_runtime_error(monkeypatch):
    def slow_transcribe(*args, **kwargs):
        def seg_gen():
            time.sleep(0.05)
            yield SimpleNamespace(start=0.0, end=1.0, text="test", words=[])
        return seg_gen(), SimpleNamespace(language="en", duration=1.0)

    fake_model = SimpleNamespace(transcribe=slow_transcribe)
    monkeypatch.setattr(transcription, "_model", fake_model)
    try:
        transcription.transcribe("dummy.mp4", timeout=0.01)
    except RuntimeError as exc:
        assert "timed out" in str(exc)
    else:
        raise AssertionError("Expected transcribe to time out")

