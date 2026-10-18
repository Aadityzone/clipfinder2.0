from pathlib import Path
import subprocess
import json

import pytest

from ai.services import download as downloader
from ai import main as ai_main


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
        "https://attacker.youtube.com/watch?v=123",
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


def test_metadata_lookup_skips_media_download_and_normalizes_result(monkeypatch):
    observed = {}
    def fake_run(args, **kwargs):
        observed["args"] = args
        observed["timeout"] = kwargs["timeout"]
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps({
            "title": "VOD", "duration": 7200, "thumbnail": "https://img.example/thumb.jpg",
            "extractor_key": "Twitch", "id": "123",
        }), stderr="")
    monkeypatch.setattr(downloader.subprocess, "run", fake_run)
    result = downloader.get_video_metadata("https://www.twitch.tv/videos/123")
    assert result["duration"] == 7200
    assert result["platform"] == "Twitch"
    assert "--skip-download" in observed["args"]
    assert "--dump-single-json" in observed["args"]
    assert observed["timeout"] == downloader.METADATA_TIMEOUT_SECONDS


def test_metadata_lookup_rejects_missing_duration(monkeypatch):
    monkeypatch.setattr(downloader.subprocess, "run", lambda args, **kwargs: subprocess.CompletedProcess(args, 0, stdout='{"title":"No duration"}', stderr=""))
    with pytest.raises(RuntimeError, match="usable video duration"):
        downloader.get_video_metadata("https://www.twitch.tv/videos/123")


def test_range_download_requests_only_the_selected_section_and_never_falls_back(tmp_path, monkeypatch):
    observed = {}
    def fake_run(args, **kwargs):
        observed["args"] = args
        observed["timeout"] = kwargs["timeout"]
        (tmp_path / "source-range.mp4").write_bytes(b"x" * 2048)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
    monkeypatch.setattr(downloader.subprocess, "run", fake_run)
    result = downloader.download_range("https://www.twitch.tv/videos/123", str(tmp_path), 3600, 7200)
    assert result.endswith("source-range.mp4")
    assert observed["args"][observed["args"].index("--download-sections") + 1] == "*3600.000-7200.000"
    assert observed["args"][observed["args"].index("--downloader") + 1] == "ffmpeg"
    assert observed["timeout"] == downloader.DOWNLOAD_TIMEOUT_SECONDS


def test_range_download_failure_is_not_retried_as_full_source(tmp_path, monkeypatch):
    observed = []
    def fake_run(args, **kwargs):
        observed.append(args)
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="section unsupported")
    monkeypatch.setattr(downloader.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="Selected source range download failed"):
        downloader.download_range("https://www.twitch.tv/videos/123", str(tmp_path), 3600, 7200)
    assert len(observed) == 1
    assert "--download-sections" in observed[0]


def test_ai_metadata_route_does_not_call_ingestion_or_download(monkeypatch):
    monkeypatch.setattr(ai_main, "auth", lambda _secret: None)
    monkeypatch.setattr(ai_main, "get_video_metadata", lambda url: {"title": "Source", "duration": 7200, "platform": "Twitch"})
    monkeypatch.setattr(ai_main, "download", lambda *_args: (_ for _ in ()).throw(AssertionError("metadata must not download media")))
    result = ai_main.source_metadata(ai_main.SourceMetadataRequest(url="https://www.twitch.tv/videos/123"), None)
    assert result["duration"] == 7200
    assert result["title"] == "Source"


def test_download_rejects_insufficient_disk_space(tmp_path, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(downloader.shutil, "disk_usage", lambda _p: SimpleNamespace(total=10**10, used=10**10 - 10**6, free=10**6))
    with pytest.raises(RuntimeError, match="Insufficient disk space"):
        downloader.download("https://www.twitch.tv/videos/123", str(tmp_path))


def test_download_cleans_up_partial_files_on_failure(tmp_path, monkeypatch):
    part_file = tmp_path / "source.mp4.part"
    part_file.write_bytes(b"corrupted partial data")
    temp_file = tmp_path / "source.temp"
    temp_file.write_bytes(b"temp data")

    def fake_run(args, **kwargs):
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="Download aborted")

    monkeypatch.setattr(downloader.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="Download aborted"):
        downloader.download("https://www.twitch.tv/videos/123", str(tmp_path))

    assert not part_file.exists()
    assert not temp_file.exists()

