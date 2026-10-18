import importlib
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

transcription = importlib.import_module("ai.transcribe")


@pytest.fixture(autouse=True)
def _clean_model_state(monkeypatch):
    """Every test starts with no cached model and no in-flight load thread."""
    monkeypatch.setattr(transcription, "_model", None)
    monkeypatch.setattr(transcription, "_load_thread", None)
    monkeypatch.setattr(transcription, "_load_result", {})


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


def test_silent_video_returns_empty_transcript_without_loading_whisper(monkeypatch):
    monkeypatch.setattr(transcription, "ffprobe", lambda _path: {
        "duration": 42.5, "hasAudio": False,
    })
    monkeypatch.setattr(
        transcription,
        "transcribe",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("Whisper must be skipped")),
    )

    result = transcription.transcribe_media("silent.mp4")

    assert result == {
        "language": "unknown", "text": "", "segments": [], "duration": 42.5,
    }


def test_silent_video_range_is_validated_and_reports_range_duration(monkeypatch):
    monkeypatch.setattr(transcription, "ffprobe", lambda _path: {
        "duration": 42.5, "hasAudio": False,
    })

    result = transcription.transcribe_media("silent.mp4", "en", 10, 20)

    assert result["language"] == "en"
    assert result["text"] == ""
    assert result["segments"] == []
    assert result["duration"] == 10


def test_silent_video_rejects_one_sided_range(monkeypatch):
    import pytest

    monkeypatch.setattr(transcription, "ffprobe", lambda _path: {
        "duration": 42.5, "hasAudio": False,
    })
    with pytest.raises(ValueError, match="Both start_seconds and end_seconds"):
        transcription.transcribe_media("silent.mp4", start_seconds=10)


def test_model_load_is_bounded_when_the_loader_stalls(monkeypatch):
    """A stalled model download must fail fast, not hold the model lock forever."""
    monkeypatch.setattr(transcription, "DEFAULT_LOAD_TIMEOUT", 0.05)
    monkeypatch.delenv("WHISPER_LOAD_TIMEOUT_SECONDS", raising=False)

    class StallingWhisperModel:
        def __init__(self, *args, **kwargs):
            time.sleep(0.6)

    monkeypatch.setattr(transcription, "WhisperModel", StallingWhisperModel)

    started = time.time()
    with pytest.raises(RuntimeError, match="did not load within"):
        transcription.model()
    elapsed = time.time() - started

    assert elapsed < 0.5, "a stalled load must be bounded, not hang"
    assert transcription._model is None, "a timed-out load must not be cached"


def test_model_load_error_is_reported_and_a_later_retry_can_succeed(monkeypatch):
    class ExplodingWhisperModel:
        def __init__(self, *args, **kwargs):
            raise OSError("model.bin is missing from the cache")

    monkeypatch.setattr(transcription, "WhisperModel", ExplodingWhisperModel)
    with pytest.raises(RuntimeError, match="could not be loaded") as failure:
        transcription.model()

    assert "OSError" in str(failure.value)
    assert "model.bin is missing" in str(failure.value)
    assert transcription._model is None, "a failed load must not poison later attempts"

    class WorkingWhisperModel:
        def __init__(self, *args, **kwargs):
            pass

    monkeypatch.setattr(transcription, "WhisperModel", WorkingWhisperModel)
    assert isinstance(transcription.model(), WorkingWhisperModel)


def test_model_load_passes_local_files_only_and_caches_one_instance(monkeypatch):
    captured = {}

    class FakeWhisperModel:
        def __init__(self, name, device=None, compute_type=None, local_files_only=None):
            captured.update(name=name, device=device, compute=compute_type, local=local_files_only)

    monkeypatch.setenv("WHISPER_MODEL", "tiny")
    monkeypatch.setenv("WHISPER_LOCAL_FILES_ONLY", "1")
    monkeypatch.delenv("WHISPER_DEVICE", raising=False)
    monkeypatch.delenv("WHISPER_COMPUTE_TYPE", raising=False)
    monkeypatch.setattr(transcription, "WhisperModel", FakeWhisperModel)

    first = transcription.model()
    second = transcription.model()

    assert isinstance(first, FakeWhisperModel)
    assert second is first
    assert captured == {"name": "tiny", "device": "auto", "compute": "int8", "local": True}


def test_local_files_only_defaults_off_so_first_run_downloads_still_work(monkeypatch):
    monkeypatch.delenv("WHISPER_LOCAL_FILES_ONLY", raising=False)
    assert transcription._env_flag("WHISPER_LOCAL_FILES_ONLY", False) is False


def test_whisper_load_timeout_parsing_rejects_invalid_values():
    assert transcription._positive_seconds(None, 300.0) == 300.0
    assert transcription._positive_seconds("45", 300.0) == 45.0
    for invalid in ("0", "-5", "nonsense", "", "inf", "nan"):
        assert transcription._positive_seconds(invalid, 300.0) == 300.0, invalid


def test_whisper_env_flag_parsing(monkeypatch):
    for raw in ("1", "true", "TRUE", "yes", "on", " 1 "):
        monkeypatch.setenv("WHISPER_LOCAL_FILES_ONLY", raw)
        assert transcription._env_flag("WHISPER_LOCAL_FILES_ONLY", False) is True, raw
    for raw in ("0", "false", "no", "off", "whatever", ""):
        monkeypatch.setenv("WHISPER_LOCAL_FILES_ONLY", raw)
        assert transcription._env_flag("WHISPER_LOCAL_FILES_ONLY", False) is False, raw


def test_transcription_capabilities_reports_load_configuration(monkeypatch):
    monkeypatch.setenv("WHISPER_LOCAL_FILES_ONLY", "1")
    monkeypatch.setenv("WHISPER_LOAD_TIMEOUT_SECONDS", "42")

    capabilities = transcription.transcription_capabilities()

    assert capabilities["available"] is True
    assert capabilities["localFilesOnly"] is True
    assert capabilities["loadTimeoutSeconds"] == 42.0
    assert capabilities["loaded"] is False

