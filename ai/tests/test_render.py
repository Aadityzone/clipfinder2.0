from unittest.mock import patch

from ai.services.render import render


def test_render_burns_ass_captions_into_final_mp4(tmp_path):
    output = tmp_path / "clip.mp4"
    captions = [{"start": 0.0, "end": 1.2, "text": "A real caption"}]

    with patch("ai.services.render.subprocess.run") as run, patch(
        "ai.services.render.validate_render_output"
    ) as validate:
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
    validate.assert_called_once_with(str(output), 4.0)


def test_render_without_captions_uses_single_render_pass(tmp_path):
    output = tmp_path / "clip.mp4"

    with patch("ai.services.render.subprocess.run") as run, patch(
        "ai.services.render.validate_render_output"
    ) as validate:
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
    validate.assert_called_once_with(str(output), 4.0)


def test_render_multiple_segments_maps_optional_audio(tmp_path):
    output = tmp_path / "clip.mp4"

    with patch("ai.services.render.subprocess.run") as run, patch(
        "ai.services.render.validate_render_output"
    ) as validate:
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
    validate.assert_called_once_with(str(output), 5.0)


def test_render_output_validation_rejects_missing_video_stream(tmp_path):
    import pytest
    from ai.services import render as render_module

    output = tmp_path / "corrupt.mp4"
    output.write_bytes(b"x" * 2048)
    with patch("ai.services.render.ffprobe", return_value={
        "duration": 4, "width": None, "height": None,
    }):
        with pytest.raises(RuntimeError, match="no valid video stream"):
            render_module.validate_render_output(str(output), 4)


def test_render_output_validation_rejects_truncated_video(tmp_path):
    import pytest
    from ai.services import render as render_module

    output = tmp_path / "truncated.mp4"
    output.write_bytes(b"x" * 2048)
    with patch("ai.services.render.ffprobe", return_value={
        "duration": 1, "width": 1080, "height": 1920,
    }):
        with pytest.raises(RuntimeError, match="does not match the expected"):
            render_module.validate_render_output(str(output), 10)

def test_render_rejects_invalid_segment_ranges_before_ffmpeg(tmp_path):
    import pytest

    output = tmp_path / "clip.mp4"
    with patch("ai.services.render.subprocess.run") as run, patch(
        "ai.services.render.validate_render_output"
    ):
        with pytest.raises(ValueError, match="end must be after"):
            render(
                input_path=str(tmp_path / "source.mp4"),
                output_path=str(output),
                segments=[{"start": 5, "end": 5}],
            )
    run.assert_not_called()


def test_render_rejects_non_finite_timestamps(tmp_path):
    import pytest

    with pytest.raises(ValueError, match="must be finite"):
        render(
            input_path=str(tmp_path / "source.mp4"),
            output_path=str(tmp_path / "clip.mp4"),
            segments=[{"start": 0, "end": float("nan")}],
        )


def test_render_sanitizes_non_finite_focus_position(tmp_path):
    output = tmp_path / "clip.mp4"
    with patch("ai.services.render.subprocess.run") as run, patch(
        "ai.services.render.validate_render_output"
    ):
        render(
            input_path=str(tmp_path / "source.mp4"),
            output_path=str(output),
            start=0,
            end=4,
            focus_x=float("nan"),
        )
    vf = run.call_args.args[0][run.call_args.args[0].index("-vf") + 1]
    assert "(iw-1080)*0.5" in vf
