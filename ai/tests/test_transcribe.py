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
