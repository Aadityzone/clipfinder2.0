import os
import subprocess
import tempfile
import math

from .captions import write_ass


FFMPEG_TIMEOUT_SECONDS = 300


def validate_segments(segments: list[dict], source_duration: float) -> tuple[list[dict], float]:
    if not segments or len(segments) > 100:
        raise ValueError("Provide between 1 and 100 render segments.")
    if not math.isfinite(source_duration) or source_duration <= 0:
        raise ValueError("Source duration must be a positive finite number.")

    normalized = []
    previous_end = -1.0
    for segment in segments:
        if not isinstance(segment, dict):
            raise ValueError("Render segments must be objects.")
        start_value, end_value = segment.get("start"), segment.get("end")
        if isinstance(start_value, bool) or isinstance(end_value, bool):
            raise ValueError("Render segment times must be numeric.")
        try:
            start, end = float(start_value), float(end_value)
        except (TypeError, ValueError):
            raise ValueError("Render segment times must be numeric.")
        if (not math.isfinite(start) or not math.isfinite(end) or start < 0
                or end <= start or end > source_duration + 0.05 or start < previous_end):
            raise ValueError("Render segments must be ordered, non-overlapping, and within the source duration.")
        normalized.append({"start": start, "end": end})
        previous_end = end
    duration = sum(segment["end"] - segment["start"] for segment in normalized)
    return normalized, duration


def validate_render_output(metadata: dict, size: int, expected_duration: float) -> None:
    duration = metadata.get("duration")
    width, height = metadata.get("width"), metadata.get("height")
    dimensions_valid = all(
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(value)
        and value > 0
        for value in (width, height)
    )
    if (
        size < 1024
        or isinstance(duration, bool)
        or not isinstance(duration, (int, float))
        or not math.isfinite(duration)
        or duration <= 0
        or not dimensions_valid
    ):
        raise ValueError("Render output is missing, empty, or not a readable video.")
    tolerance = max(0.75, expected_duration * 0.05)
    if abs(float(duration) - expected_duration) > tolerance:
        raise ValueError("Render output duration does not match the requested edit.")


def _escape_filter_path(path: str) -> str:
    """Escape a filesystem path for FFmpeg's filter-argument parser."""
    return path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def render(
    input_path: str,
    output_path: str,
    start: float = 0,
    end: float | None = None,
    aspect: str = "9:16",
    segments: list[dict] | None = None,
    captions: list[dict] | None = None,
    caption_style: dict | None = None,
    focus_x: float = 0.5,
):
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    segs = segments or [{"start": start, "end": end if end is not None else start + 0.01}]
    focus_x = max(0.0, min(1.0, float(focus_x)))
    vf = {
        "9:16": f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920:(iw-1080)*{focus_x}:0",
        "1:1": f"scale=1080:1080:force_original_aspect_ratio=increase,crop=1080:1080:(iw-1080)*{focus_x}:0",
        "16:9": "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080:(iw-1920)*0.5:0",
    }.get(
        aspect,
        "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080:(iw-1920)*0.5:0",
    )

    # Explicitly map the video and optionally map audio. Some valid source
    # videos (for example, muted gameplay captures) contain no audio stream;
    # requiring -af/-c:a without an audio stream makes FFmpeg fail those jobs.
    stream_args = ["-map", "0:v:0", "-map", "0:a?"]

    def render_base(base_output: str):
        if len(segs) == 1:
            segment = segs[0]
            duration = max(0.01, float(segment["end"]) - float(segment["start"]))
            subprocess.run(
                [
                    "ffmpeg", "-y", "-ss", str(segment["start"]), "-i", input_path,
                    "-t", str(duration), "-vf", vf, *stream_args, "-c:v", "libx264",
                    "-preset", "veryfast", "-crf", "20", "-c:a", "aac",
                    "-movflags", "+faststart", base_output,
                ],
                check=True,
                timeout=FFMPEG_TIMEOUT_SECONDS,
            )
            return

        with tempfile.TemporaryDirectory(prefix="clipfinder-render-") as directory:
            parts = []
            for index, segment in enumerate(segs):
                part_path = os.path.join(directory, f"part-{index}.mp4")
                duration = max(0.01, float(segment["end"]) - float(segment["start"]))
                subprocess.run(
                    [
                        "ffmpeg", "-y", "-ss", str(segment["start"]), "-i", input_path,
                        "-t", str(duration), "-vf", vf, *stream_args, "-c:v", "libx264",
                        "-preset", "veryfast", "-crf", "20", "-c:a", "aac",
                        "-movflags", "+faststart", part_path,
                    ],
                    check=True,
                    timeout=FFMPEG_TIMEOUT_SECONDS,
                )
                parts.append(part_path)

            concat_path = os.path.join(directory, "concat.txt")
            with open(concat_path, "w", encoding="utf-8") as file:
                for part_path in parts:
                    file.write("file " + repr(part_path) + "\n")

            subprocess.run(
                [
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_path,
                    "-c", "copy", "-movflags", "+faststart", base_output,
                ],
                check=True,
                timeout=FFMPEG_TIMEOUT_SECONDS,
            )

    if not captions:
        render_base(output_path)
        return

    # Burn captions after assembling the complete edit so cue timestamps remain
    # relative to the final clip, including edits with multiple source segments.
    with tempfile.TemporaryDirectory(prefix="clipfinder-caption-") as directory:
        base_path = os.path.join(directory, "base.mp4")
        ass_path = os.path.join(directory, "captions.ass")
        render_base(base_path)
        write_ass(captions, ass_path, caption_style)
        subtitles_filter = "ass='" + _escape_filter_path(ass_path) + "'"
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", base_path, "-vf", subtitles_filter,
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-c:a", "copy", "-movflags", "+faststart", output_path,
            ],
            check=True,
            timeout=FFMPEG_TIMEOUT_SECONDS,
        )
