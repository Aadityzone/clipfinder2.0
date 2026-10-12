from unittest.mock import patch

import pytest

from ai.services.render import render, validate_render_output, validate_segments


@pytest.mark.parametrize("segments", [
    [{"start": -1, "end": 2}],
    [{"start": 2, "end": 1}],
    [{"start": 0, "end": 2}, {"start": 1, "end": 3}],
    [{"start": 0, "end": 11}],
    [{"start": float("nan"), "end": 2}],
])
def test_render_segments_reject_invalid_source_timestamps(segments):
    with pytest.raises(ValueError):
        validate_segments(segments, 10)


def test_render_segments_preserve_valid_disjoint_source_ranges():
    segments, duration = validate_segments([
        {"start": 1, "end": 3}, {"start": 5.5, "end": 7},
    ], 10)

    assert segments == [{"start": 1.0, "end": 3.0}, {"start": 5.5, "end": 7.0}]
    assert duration == 3.5


@pytest.mark.parametrize(("metadata", "size", "expected"), [
    ({"duration": 3, "width": 1080, "height": 1920}, 100, 3),
    ({"duration": 0, "width": 1080, "height": 1920}, 2048, 3),
    ({"duration": 3, "width": None, "height": 1920}, 2048, 3),
    ({"duration": 8, "width": 1080, "height": 1920}, 2048, 3),
])
def test_render_output_rejects_empty_or_invalid_video(metadata, size, expected):
    with pytest.raises(ValueError):
        validate_render_output(metadata, size, expected)


def test_render_output_accepts_probe_valid_video_with_expected_duration():
    validate_render_output({"duration": 3.2, "width": 1080, "height": 1920}, 2048, 3)


def test_render_burns_ass_captions_into_final_mp4(tmp_path):
    output = tmp_path / "clip.mp4"
    captions = [{"start": 0.0, "end": 1.2, "text": "A real caption"}]

    with patch("ai.services.render.subprocess.run") as run:
        render(
            input_path=str(tmp_path / "source.mp4"),
            output_path=str(output),
            start=0,
            end=4,
            captions=captions,
            caption_style={"font": "Arial", "size": 32},
        )

    assert run.call_count == 2
    base_command = run.call_args_list[0].args[0]
    assert base_command[base_command.index("-map") + 1] == "0:v:0"
    assert base_command[base_command.index("-map", base_command.index("-map") + 1) + 1] == "0:a?"
    assert "-af" not in base_command
    final_command = run.call_args_list[-1].args[0]
    assert "-vf" in final_command
    assert "ass=" in final_command[final_command.index("-vf") + 1]
    assert str(output) == final_command[-1]
    assert run.call_args_list[-1].kwargs["check"] is True


def test_render_without_captions_uses_single_render_pass(tmp_path):
    output = tmp_path / "clip.mp4"

    with patch("ai.services.render.subprocess.run") as run:
        render(
            input_path=str(tmp_path / "source.mp4"),
            output_path=str(output),
            start=0,
            end=4,
        )

    assert run.call_count == 1
    command = run.call_args.args[0]
    assert "-map" in command
    assert "0:a?" in command
    assert "-vf" in command
    assert str(output) == command[-1]


def test_render_multiple_segments_maps_optional_audio(tmp_path):
    output = tmp_path / "clip.mp4"

    with patch("ai.services.render.subprocess.run") as run:
        render(
            input_path=str(tmp_path / "source.mp4"),
            output_path=str(output),
            segments=[{"start": 0, "end": 2}, {"start": 5, "end": 8}],
        )

    assert run.call_count == 3
    for call in run.call_args_list[:2]:
        command = call.args[0]
        assert "0:a?" in command
        assert "-map" in command


def test_render_subprocesses_have_a_hard_timeout(tmp_path):
    from ai.services.render import FFMPEG_TIMEOUT_SECONDS

    output = tmp_path / "clip.mp4"
    with patch("ai.services.render.subprocess.run") as run:
        render(input_path=str(tmp_path / "source.mp4"), output_path=str(output), start=0, end=4)

    assert run.call_count == 1
    assert run.call_args.kwargs["timeout"] == FFMPEG_TIMEOUT_SECONDS
    assert FFMPEG_TIMEOUT_SECONDS == 300


def test_render_propagates_ffmpeg_timeout_for_worker_failure_handling(tmp_path):
    import subprocess

    output = tmp_path / "clip.mp4"
    with patch(
        "ai.services.render.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="ffmpeg", timeout=300),
    ):
        with pytest.raises(subprocess.TimeoutExpired):
            render(input_path=str(tmp_path / "source.mp4"), output_path=str(output), start=0, end=4)
