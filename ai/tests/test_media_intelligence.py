import subprocess
from types import SimpleNamespace

from ai.services import media_intelligence

def test_scene_detection_uses_bounded_downscaled_sampling(monkeypatch, tmp_path):
    media = tmp_path / "source.mp4"
    media.write_bytes(b"source")
    observed = {}

    def fake_run(command, **kwargs):
        observed["filter"] = command[command.index("-vf") + 1]
        observed["timeout"] = kwargs.get("timeout")
        return SimpleNamespace(
            returncode=0,
            stderr="frame pts_time:1.500\nframe pts_time:3.000\n",
        )

    monkeypatch.setattr(media_intelligence.subprocess, "run", fake_run)
    result = media_intelligence.scene_features(str(media))

    assert result == {"sceneChanges": [1.5, 3.0], "sceneChangeCount": 2}
    assert "fps=2" in observed["filter"]
    assert "scale=320:-2" in observed["filter"]
    assert observed["timeout"] == 600


def test_scene_detection_failure_degrades_without_failing_analysis(monkeypatch, tmp_path):
    media = tmp_path / "source.mp4"
    media.write_bytes(b"source")
    monkeypatch.setattr(
        media_intelligence.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(subprocess.TimeoutExpired("ffmpeg", 600)),
    )

    assert media_intelligence.scene_features(str(media)) == {}


def test_audio_features_timeout_degrades_gracefully(monkeypatch, tmp_path):
    media = tmp_path / "source.mp4"
    media.write_bytes(b"source")
    monkeypatch.setattr(
        media_intelligence.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(subprocess.TimeoutExpired("ffmpeg", 300)),
    )
    features, windows = media_intelligence.audio_features(str(media))
    assert features["meanDb"] is None
    assert windows == []
    assert features["windowCount"] == 0


def test_audio_features_reuses_window_measurements_without_a_second_decode(monkeypatch, tmp_path):
    """Regression: loudness must come from the windowed pass, not a second decode."""
    media = tmp_path / "source.mp4"
    media.write_bytes(b"source")
    decodes = []

    def fail_if_called(*_args, **_kwargs):
        decodes.append("ffmpeg")
        raise AssertionError("audio_features must not run its own ffmpeg decode")

    monkeypatch.setattr(media_intelligence.subprocess, "run", fail_if_called)
    monkeypatch.setattr(media_intelligence, "loudness_windows", lambda _path: [
        {"start": 0.0, "end": 5.0, "meanDb": -30.0, "peakDb": -6.0, "energy": 0.33},
        {"start": 5.0, "end": 10.0, "meanDb": -20.0, "peakDb": -3.0, "energy": 0.55},
    ])

    features, windows = media_intelligence.audio_features(str(media))

    assert decodes == []
    assert features == {
        "meanDb": -25.0, "peakDb": -3.0, "durationS": 10.0, "windowCount": 2,
    }
    assert len(windows) == 2


def test_audio_features_ignores_non_finite_window_measurements(monkeypatch, tmp_path):
    media = tmp_path / "source.mp4"
    media.write_bytes(b"source")
    monkeypatch.setattr(media_intelligence, "loudness_windows", lambda _path: [
        {"start": 0.0, "end": 5.0, "meanDb": float("nan"), "peakDb": None},
        {"start": 5.0, "end": 10.0, "meanDb": -18.0, "peakDb": -4.0},
    ])

    features, _ = media_intelligence.audio_features(str(media))

    assert features["meanDb"] == -18.0
    assert features["peakDb"] == -4.0
    assert features["durationS"] == 10.0


def test_analyze_media_isolates_a_failing_optional_signal(monkeypatch, tmp_path):
    """One broken detector must not break the whole analysis."""
    media = tmp_path / "source.mp4"
    media.write_bytes(b"source")
    monkeypatch.setattr(
        media_intelligence,
        "scene_features",
        lambda _path: (_ for _ in ()).throw(RuntimeError("ffmpeg exploded")),
    )
    monkeypatch.setattr(
        media_intelligence,
        "face_features",
        lambda _path: (_ for _ in ()).throw(RuntimeError("no cascade")),
    )
    monkeypatch.setattr(media_intelligence, "audio_features", lambda _path: (
        {"meanDb": -20.0, "peakDb": -2.0, "durationS": 3.0, "windowCount": 1},
        [{"start": 0.0, "end": 3.0, "meanDb": -20.0, "peakDb": -2.0, "energy": 0.5}],
    ))
    monkeypatch.setattr(media_intelligence, "sample_visual_features", lambda _path: {"available": False, "samples": []})
    monkeypatch.setattr(media_intelligence, "analyze_on_screen", lambda _path: {"available": False, "samples": []})

    result = media_intelligence.analyze_media(str(media))

    assert result["scenes"] == {}
    assert result["vision"] == {}
    assert result["audioWindows"][0]["energy"] == 0.5
    assert result["visual"]["available"] is False


def test_face_features_degrades_without_raising_on_unreadable_media(tmp_path):
    media = tmp_path / "not-a-video.mp4"
    media.write_bytes(b"this is not a video")

    result = media_intelligence.face_features(str(media))

    assert result["available"] is False
    assert result["faces"] == []
    assert result["reason"]


def test_face_features_degrades_when_opencv_raises(monkeypatch, tmp_path):
    import cv2

    media = tmp_path / "source.mp4"
    media.write_bytes(b"source")
    monkeypatch.setattr(
        cv2,
        "VideoCapture",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(cv2.error("no backend")),
    )

    result = media_intelligence.face_features(str(media))

    assert result["available"] is False
    assert result["faces"] == []
    assert "face detection failed" in result["reason"]


def test_face_features_reports_missing_media(tmp_path):
    result = media_intelligence.face_features(str(tmp_path / "missing.mp4"))

    assert result == {"available": False, "faces": [], "reason": "media not found"}


def test_ffprobe_timeout_raises_runtime_error(monkeypatch, tmp_path):
    from ai.services.media import ffprobe
    media = tmp_path / "source.mp4"
    media.write_bytes(b"source")
    import ai.services.media as media_mod
    monkeypatch.setattr(
        media_mod.subprocess,
        "check_output",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(subprocess.TimeoutExpired("ffprobe", 60)),
    )
    try:
        ffprobe(str(media))
    except RuntimeError as exc:
        assert "timed out" in str(exc)
    else:
        raise AssertionError("Expected ffprobe to raise RuntimeError on timeout")


