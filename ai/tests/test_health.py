from ai import main


def test_health_reports_ready_when_media_binaries_exist(monkeypatch):
    available = {"ffmpeg", "ffprobe", "yt-dlp"}
    monkeypatch.setattr(main.shutil, "which", lambda name: f"/usr/bin/{name}" if name in available else None)

    result = main.health()

    assert result["ok"] is True
    assert result["service"] == "ai"
    assert result["dependencies"] == {
        "ffmpeg": True,
        "ffprobe": True,
        "yt_dlp": True,
    }


def test_health_reports_not_ready_when_a_required_binary_is_missing(monkeypatch):
    available = {"ffmpeg", "yt-dlp"}
    monkeypatch.setattr(main.shutil, "which", lambda name: f"/usr/bin/{name}" if name in available else None)

    result = main.health()

    assert result["ok"] is False
    assert result["dependencies"]["ffmpeg"] is True
    assert result["dependencies"]["ffprobe"] is False
    assert result["dependencies"]["yt_dlp"] is True
