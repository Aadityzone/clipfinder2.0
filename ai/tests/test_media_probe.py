import json
import subprocess

import pytest

from ai.services import media


def test_ffprobe_uses_a_bounded_subprocess_timeout(monkeypatch):
    observed = {}

    def fake_check_output(command, **kwargs):
        observed["command"] = command
        observed.update(kwargs)
        return json.dumps({
            "streams": [
                {"codec_type": "video", "width": 1920, "height": 1080, "r_frame_rate": "60/1", "codec_name": "h264"},
                {"codec_type": "audio"},
            ],
            "format": {"duration": "12.5"},
        })

    monkeypatch.setattr(media.subprocess, "check_output", fake_check_output)

    result = media.ffprobe("source.mp4")

    assert observed["timeout"] == media.FFPROBE_TIMEOUT_SECONDS
    assert observed["command"][0] == "ffprobe"
    assert result == {
        "duration": 12.5,
        "width": 1920,
        "height": 1080,
        "fps": 60.0,
        "codec": "h264",
        "hasAudio": True,
    }


def test_ffprobe_timeout_propagates_for_caller_to_handle(monkeypatch):
    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired("ffprobe", media.FFPROBE_TIMEOUT_SECONDS)

    monkeypatch.setattr(media.subprocess, "check_output", timeout)

    with pytest.raises(subprocess.TimeoutExpired):
        media.ffprobe("unreadable.mp4")


@pytest.mark.parametrize("duration", ["nan", "inf", "-1", "not-a-number"])
def test_ffprobe_normalizes_invalid_duration(duration, monkeypatch):
    monkeypatch.setattr(
        media.subprocess,
        "check_output",
        lambda *_args, **_kwargs: json.dumps({
            "streams": [{"codec_type": "video", "width": 640, "height": 360, "r_frame_rate": "0/0"}],
            "format": {"duration": duration},
        }),
    )

    result = media.ffprobe("source.mp4")

    assert result["duration"] == 0
    assert result["fps"] is None
