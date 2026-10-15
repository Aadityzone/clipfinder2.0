import subprocess
from types import SimpleNamespace

import pytest

from ai.services.analysis_range import (
    extract_analysis_range,
    shift_segments_to_range,
    validate_analysis_range,
)


def test_validate_analysis_range_enforces_duration_and_one_hour_limit():
    assert validate_analysis_range(30, 90, 100) == (30.0, 90.0)
    with pytest.raises(ValueError, match="one hour"):
        validate_analysis_range(0, 3600.1, 4000)
    with pytest.raises(ValueError, match="beyond"):
        validate_analysis_range(90, 101, 100)
    with pytest.raises(ValueError, match="finite"):
        validate_analysis_range(0, float("inf"), 100)


def test_shift_segments_clips_to_range_and_restores_local_time():
    segments = [
        {"start": 25, "end": 32, "text": "starts before range"},
        {"start": 35, "end": 42, "text": "inside range"},
        {"start": 58, "end": 65, "text": "ends after range"},
        {"start": 70, "end": 75, "text": "outside range"},
        {"start": "bad", "end": 90, "text": "invalid"},
    ]
    result = shift_segments_to_range(segments, 30, 60)
    assert [(row["start"], row["end"]) for row in result] == [(0.0, 2.0), (5.0, 12.0), (28.0, 30.0)]
    assert result[0]["text"] == "starts before range"


def test_extract_analysis_range_uses_bounded_low_resolution_ffmpeg(monkeypatch, tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    output = tmp_path / "range.mp4"
    observed = {}

    def fake_run(command, **kwargs):
        observed["command"] = command
        observed["timeout"] = kwargs["timeout"]
        output.write_bytes(b"x" * 2048)
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr("ai.services.analysis_range.subprocess.run", fake_run)
    assert extract_analysis_range(str(source), 120, 150, str(output)) == str(output)
    command = observed["command"]
    assert command[command.index("-ss") + 1] == "120.0"
    assert command[command.index("-t") + 1] == "30.0"
    assert "fps=2,scale=640:-2" in command
    assert observed["timeout"] == 1800


def test_extract_analysis_range_reports_ffmpeg_errors(monkeypatch, tmp_path):
    def fail(*_args, **_kwargs):
        raise subprocess.CalledProcessError(1, ["ffmpeg"], stderr="decode error")

    monkeypatch.setattr("ai.services.analysis_range.subprocess.run", fail)
    with pytest.raises(RuntimeError, match="decode error"):
        extract_analysis_range("source.mp4", 0, 10, str(tmp_path / "range.mp4"))
