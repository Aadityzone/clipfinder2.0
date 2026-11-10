"""Tests for Phase 2 Production-Grade Video Source Acquisition & Media Infrastructure."""

import json
import subprocess
from pathlib import Path

import pytest

from ai.services import download as downloader
from ai.services import media


@pytest.fixture(autouse=True)
def _public_dns_for_url_validation(monkeypatch):
    """Keep URL-validation unit tests deterministic and independent of live DNS."""
    def resolve_public(host, *_args, **_kwargs):
        # Keep localhost private while making public provider DNS deterministic.
        address = "127.0.0.1" if host.rstrip(".").lower() == "localhost" else "93.184.216.34"
        return [(downloader.socket.AF_INET, downloader.socket.SOCK_STREAM, 6, "", (address, 0))]

    monkeypatch.setattr(downloader.socket, "getaddrinfo", resolve_public)


# --- URL Validation Tests ---

def test_validate_video_url_accepts_youtube_variants():
    urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtube.com/watch?v=dQw4w9WgXcQ",
        "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ",
    ]
    for url in urls:
        assert downloader.validate_video_url(url) == url


def test_validate_video_url_accepts_twitch_and_kick():
    urls = [
        "https://www.twitch.tv/videos/1234567890",
        "https://twitch.tv/videos/1234567890",
        "https://clips.twitch.tv/AcceptableClipName-123",
        "https://www.twitch.tv/streamer/clip/ClipName123",
        "https://kick.com/streamer",
        "https://www.kick.com/video/123456",
    ]
    for url in urls:
        assert downloader.validate_video_url(url) == url


def test_validate_video_url_accepts_direct_public_media():
    urls = [
        "https://cdn.example.com/media/clip.mp4",
        "https://storage.googleapis.com/bucket/sample.webm",
        "https://media.org/sample.mov",
        "http://public-video.org/test.mkv",
    ]
    for url in urls:
        assert downloader.validate_video_url(url) == url


def test_validate_video_url_rejects_ssrf_and_private_ips():
    dangerous_urls = [
        "http://127.0.0.1/video.mp4",
        "http://localhost:80/stream.mp4",
        "https://10.0.0.1/video.mp4",
        "https://192.168.1.100/video.mp4",
        "https://172.16.0.5/video.mp4",
        "http://169.254.169.254/latest/meta-data/",
        "http://0.0.0.0/video.mp4",
    ]
    for url in dangerous_urls:
        with pytest.raises(ValueError):
            downloader.validate_video_url(url)


def test_validate_video_url_rejects_hostnames_resolving_to_private_addresses(monkeypatch):
    def resolve_private(_host, *_args, **_kwargs):
        return [(downloader.socket.AF_INET, downloader.socket.SOCK_STREAM, 6, "", ("10.1.2.3", 0))]

    monkeypatch.setattr(downloader.socket, "getaddrinfo", resolve_private)
    with pytest.raises(ValueError, match="local or private"):
        downloader.validate_video_url("https://media.example.com/clip.mp4")


def test_validate_video_url_rejects_mixed_public_and_private_dns_answers(monkeypatch):
    def resolve_mixed(_host, *_args, **_kwargs):
        return [
            (downloader.socket.AF_INET, downloader.socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0)),
            (downloader.socket.AF_INET, downloader.socket.SOCK_STREAM, 6, "", ("192.168.1.10", 0)),
        ]

    monkeypatch.setattr(downloader.socket, "getaddrinfo", resolve_mixed)
    with pytest.raises(ValueError, match="local or private"):
        downloader.validate_video_url("https://media.example.com/clip.mp4")


def test_check_disk_space_fails_closed_when_capacity_cannot_be_read(tmp_path, monkeypatch):
    def unavailable(_directory):
        raise OSError("disk usage unavailable")

    monkeypatch.setattr(downloader.shutil, "disk_usage", unavailable)
    with pytest.raises(downloader.StorageLimitError, match="Could not verify available disk space"):
        downloader.check_disk_space(tmp_path)


def test_validate_video_url_rejects_credentials_and_nonstandard_ports():
    with pytest.raises(ValueError, match="embedded credentials"):
        downloader.validate_video_url("https://admin:pass@youtube.com/watch?v=123")
    with pytest.raises(ValueError, match="standard web port"):
        downloader.validate_video_url("https://youtube.com:8443/watch?v=123")


# --- Error Classification Tests ---

def test_classify_acquisition_error_detects_private_or_deleted():
    err1 = downloader.classify_acquisition_error("ERROR: Video unavailable. This video is private.")
    assert isinstance(err1, downloader.PrivateOrDeletedVideoError)

    err2 = downloader.classify_acquisition_error("ERROR: This video has been removed by the uploader.")
    assert isinstance(err2, downloader.PrivateOrDeletedVideoError)

    err3 = downloader.classify_acquisition_error("HTTP Error 404: Not Found")
    assert isinstance(err3, downloader.PrivateOrDeletedVideoError)


def test_classify_acquisition_error_detects_restricted_or_age_gated():
    err1 = downloader.classify_acquisition_error("Sign in to confirm your age. This video may be inappropriate.")
    assert isinstance(err1, downloader.RestrictedVideoError)

    err2 = downloader.classify_acquisition_error("ERROR: The uploader has not made this video available in your country (geo-restricted).")
    assert isinstance(err2, downloader.RestrictedVideoError)


def test_classify_acquisition_error_detects_transient_network_errors():
    err1 = downloader.classify_acquisition_error("urllib.error.URLError: <urlopen error timed out>")
    assert isinstance(err1, downloader.TransientNetworkError)

    err2 = downloader.classify_acquisition_error("HTTP Error 504: Gateway Timeout")
    assert isinstance(err2, downloader.TransientNetworkError)

    err3 = downloader.classify_acquisition_error("Connection reset by peer")
    assert isinstance(err3, downloader.TransientNetworkError)


# --- Bounded Retries & Resumption ---

def test_download_retries_transient_network_fault_and_succeeds(tmp_path, monkeypatch):
    attempts = []

    def fake_run(args, **kwargs):
        attempts.append(len(attempts) + 1)
        if len(attempts) == 1:
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="urlopen error timed out")
        # Second attempt succeeds
        (tmp_path / "source.mp4").write_bytes(b"dummy mp4 media")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(downloader.subprocess, "run", fake_run)
    monkeypatch.setattr(downloader.time, "sleep", lambda _s: None)

    out = downloader.download("https://www.youtube.com/watch?v=abc", str(tmp_path))
    assert out.endswith("source.mp4")
    assert len(attempts) == 2


def test_download_does_not_retry_permanent_failure(tmp_path, monkeypatch):
    attempts = []

    def fake_run(args, **kwargs):
        attempts.append(len(attempts) + 1)
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="This video has been removed")

    monkeypatch.setattr(downloader.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="removed"):
        downloader.download("https://www.youtube.com/watch?v=abc", str(tmp_path))
    assert len(attempts) == 1


# --- FFprobe & Media Compatibility Tests ---

def test_ffprobe_parses_complete_media_metadata(tmp_path, monkeypatch):
    sample_file = tmp_path / "test.mp4"
    sample_file.write_bytes(b"x" * 1024)

    fake_output = {
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "r_frame_rate": "30/1",
                "avg_frame_rate": "30/1",
                "display_aspect_ratio": "16:9",
                "bit_rate": "4500000",
            },
            {
                "codec_type": "audio",
                "codec_name": "aac",
                "bit_rate": "192000",
                "channels": 2,
            },
        ],
        "format": {
            "duration": "120.5",
            "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
            "size": "67500000",
            "bit_rate": "4692000",
        },
    }

    monkeypatch.setattr(
        media.subprocess,
        "check_output",
        lambda *args, **kwargs: json.dumps(fake_output),
    )

    info = media.ffprobe(str(sample_file))
    assert info["duration"] == 120.5
    assert info["width"] == 1920
    assert info["height"] == 1080
    assert info["fps"] == 30.0
    assert info["codec"] == "h264"
    assert info["hasAudio"] is True
    assert info["audioCodec"] == "aac"
    assert info["audioStreamsCount"] == 1
    assert info["videoStreamsCount"] == 1
    assert info["aspectRatio"] == "16:9"
    assert info["bitrate"] == 4692000
    assert info["isVfr"] is False
    assert info["formatName"] == "mov,mp4,m4a,3gp,3g2,mj2"
    assert info["isCorrupted"] is False


def test_ffprobe_detects_variable_frame_rate(tmp_path, monkeypatch):
    sample_file = tmp_path / "vfr_sample.mp4"
    sample_file.write_bytes(b"x" * 1024)

    fake_output = {
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1280,
                "height": 720,
                "r_frame_rate": "60/1",
                "avg_frame_rate": "29.97/1",  # Significant deviation > 1%
            }
        ],
        "format": {"duration": "60.0", "size": "1000000"},
    }

    monkeypatch.setattr(
        media.subprocess,
        "check_output",
        lambda *args, **kwargs: json.dumps(fake_output),
    )

    info = media.ffprobe(str(sample_file))
    assert info["isVfr"] is True
    assert info["is_vfr"] is True


def test_ffprobe_handles_missing_audio_track(tmp_path, monkeypatch):
    sample_file = tmp_path / "silent.mp4"
    sample_file.write_bytes(b"x" * 1024)

    fake_output = {
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "r_frame_rate": "30/1",
            }
        ],
        "format": {"duration": "10.0"},
    }

    monkeypatch.setattr(
        media.subprocess,
        "check_output",
        lambda *args, **kwargs: json.dumps(fake_output),
    )

    info = media.ffprobe(str(sample_file))
    assert info["hasAudio"] is False
    assert info["audioCodec"] is None
    assert info["audioStreamsCount"] == 0


def test_ffprobe_detects_multi_audio_tracks(tmp_path, monkeypatch):
    sample_file = tmp_path / "multitrack.mp4"
    sample_file.write_bytes(b"x" * 1024)

    fake_output = {
        "streams": [
            {"codec_type": "video", "codec_name": "hevc", "width": 3840, "height": 2160, "r_frame_rate": "60/1"},
            {"codec_type": "audio", "codec_name": "aac"},
            {"codec_type": "audio", "codec_name": "opus"},
        ],
        "format": {"duration": "300.0"},
    }

    monkeypatch.setattr(
        media.subprocess,
        "check_output",
        lambda *args, **kwargs: json.dumps(fake_output),
    )

    info = media.ffprobe(str(sample_file))
    assert info["hasAudio"] is True
    assert info["audioStreamsCount"] == 2
    assert info["videoStreamsCount"] == 1


def test_ffprobe_detects_corrupted_empty_file(tmp_path):
    empty_file = tmp_path / "empty.mp4"
    empty_file.write_bytes(b"")

    info = media.ffprobe(str(empty_file), strict=False)
    assert info["isCorrupted"] is True
    assert info["duration"] == 0.0

    with pytest.raises(media.CorruptedMediaError):
        media.ffprobe(str(empty_file), strict=True)

