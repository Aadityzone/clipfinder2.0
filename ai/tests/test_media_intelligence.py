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

