from unittest.mock import patch

from ai.services.render import render


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
