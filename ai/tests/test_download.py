from pathlib import Path
import subprocess

import pytest

from ai.services import download as downloader


def test_twitch_vod_url_is_accepted():
    url = "https://www.twitch.tv/videos/2889984350"
    assert downloader.validate_video_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://127.0.0.1/private",
        "http://localhost/admin",
        "https://twitch.tv.evil.example/video",
        "https://user:password@www.twitch.tv/videos/123",
        "not-a-url",
    ],
)
def test_unsupported_or_unsafe_urls_are_rejected(url):
    with pytest.raises(ValueError):
        downloader.validate_video_url(url)


def test_download_prefers_completed_mp4_and_ignores_partial_files(tmp_path, monkeypatch):
    def fake_run(args, **kwargs):
        assert args[0] == "yt-dlp"
        assert "--no-playlist" in args
        assert args[-1] == "https://www.twitch.tv/videos/2889984350"
        assert kwargs["timeout"] == downloader.DOWNLOAD_TIMEOUT_SECONDS
        (tmp_path / "source.webm").write_bytes(b"webm")
        (tmp_path / "source.mp4.part").write_bytes(b"partial")
        (tmp_path / "source.mp4").write_bytes(b"mp4")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(downloader.subprocess, "run", fake_run)
    result = downloader.download(
        "https://www.twitch.tv/videos/2889984350",
        str(tmp_path),
    )
    assert result == str(tmp_path / "source.mp4")


def test_download_reports_provider_error(tmp_path, monkeypatch):
    def fake_run(args, **kwargs):
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="VOD unavailable")

    monkeypatch.setattr(downloader.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="VOD unavailable"):
        downloader.download("https://www.twitch.tv/videos/2889984350", str(tmp_path))


def test_download_reports_missing_ytdlp(tmp_path, monkeypatch):
    def fake_run(*args, **kwargs):
        raise FileNotFoundError("yt-dlp")

    monkeypatch.setattr(downloader.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="yt-dlp is not installed"):
        downloader.download("https://www.twitch.tv/videos/2889984350", str(tmp_path))

def test_download_reports_timeout(tmp_path, monkeypatch):
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="yt-dlp", timeout=downloader.DOWNLOAD_TIMEOUT_SECONDS)

    monkeypatch.setattr(downloader.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="timed out after 3 hours"):
        downloader.download("https://www.twitch.tv/videos/2889984350", str(tmp_path))


def test_download_rejects_empty_output(tmp_path, monkeypatch):
    def fake_run(args, **kwargs):
        (tmp_path / "source.mp4.part").write_bytes(b"partial")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(downloader.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="no complete media file"):
        downloader.download("https://www.twitch.tv/videos/2889984350", str(tmp_path))
