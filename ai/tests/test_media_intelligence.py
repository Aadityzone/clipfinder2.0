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


