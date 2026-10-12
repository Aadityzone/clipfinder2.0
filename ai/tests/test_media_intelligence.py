from subprocess import TimeoutExpired

from ai.services import media_intelligence as media


def test_audio_features_missing_file_always_returns_summary_and_windows(monkeypatch):
    monkeypatch.setattr(media.os.path, "isfile", lambda _path: False)

    summary, windows = media.audio_features("missing.mp4")

    assert summary == {}
    assert windows == []


def test_audio_features_survives_ffmpeg_timeout(monkeypatch):
    monkeypatch.setattr(media.os.path, "isfile", lambda _path: True)

    def timeout(*_args, **_kwargs):
        raise TimeoutExpired("ffmpeg", 90)

    monkeypatch.setattr(media.subprocess, "run", timeout)
    monkeypatch.setattr(media, "loudness_windows", lambda _path: [])

    summary, windows = media.audio_features("long.mp4")

    assert summary["meanDb"] is None
    assert summary["peakDb"] is None
    assert summary["durationS"] is None
    assert summary["windowCount"] == 0
    assert windows == []


def test_audio_features_parses_ffmpeg_summary(monkeypatch):
    class Result:
        stderr = (
            "Duration: 00:02:03.50, start: 0.0, bitrate: 123 kb/s\n"
            "mean_volume: -22.4 dB\nmax_volume: -1.0 dB\n"
        )

    monkeypatch.setattr(media.os.path, "isfile", lambda _path: True)
    monkeypatch.setattr(media.subprocess, "run", lambda *_args, **_kwargs: Result())
    monkeypatch.setattr(
        media, "loudness_windows",
        lambda _path: [{"start": 0, "end": 5, "energy": 0.5}],
    )

    summary, windows = media.audio_features("valid.mp4")

    assert summary["meanDb"] == -22.4
    assert summary["peakDb"] == -1.0
    assert summary["durationS"] == 123.5
    assert summary["windowCount"] == 1
    assert len(windows) == 1


def test_analyze_media_keeps_partial_results_when_optional_stages_fail(monkeypatch):
    monkeypatch.setattr(media, "audio_features", lambda _path: ({"meanDb": -20}, []))
    monkeypatch.setattr(media, "sample_visual_features", lambda _path: (_ for _ in ()).throw(RuntimeError()))
    monkeypatch.setattr(media, "analyze_on_screen", lambda _path: (_ for _ in ()).throw(ValueError()))
    monkeypatch.setattr(media, "scene_features", lambda _path: (_ for _ in ()).throw(TimeoutExpired("ffmpeg", 120)))
    monkeypatch.setattr(media, "face_features", lambda _path: {"available": True, "faces": []})

    result = media.analyze_media("partially-readable.mp4")

    assert result["audio"] == {"meanDb": -20}
    assert result["audioWindows"] == []
    assert result["visual"]["available"] is False
    assert result["onScreen"]["available"] is False
    assert result["scenes"]["available"] is False
    assert result["vision"]["available"] is True
