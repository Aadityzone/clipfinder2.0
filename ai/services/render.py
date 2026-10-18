import math
import os
import subprocess
import tempfile

from .captions import write_ass


def _escape_filter_path(path: str) -> str:
    """Escape a filesystem path for FFmpeg's filter-argument parser."""
    return path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _normalize_segments(
    start: float,
    end: float | None,
    segments: list[dict] | None,
) -> list[dict[str, float]]:
    """Reject invalid edit ranges before invoking FFmpeg."""
    source = segments or [{
        "start": start,
        "end": end if end is not None else float(start) + 0.01,
    }]
    normalized: list[dict[str, float]] = []
    for index, segment in enumerate(source):
        if not isinstance(segment, dict):
            raise ValueError(f"Render segment {index + 1} must be an object.")
        try:
            segment_start = float(segment["start"])
            segment_end = float(segment["end"])
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"Render segment {index + 1} needs numeric start and end.") from exc
        if not math.isfinite(segment_start) or not math.isfinite(segment_end):
            raise ValueError(f"Render segment {index + 1} timestamps must be finite.")
        if segment_start < 0:
            raise ValueError(f"Render segment {index + 1} cannot start before zero.")
        if segment_end <= segment_start:
            raise ValueError(f"Render segment {index + 1} end must be after its start.")
        normalized.append({"start": segment_start, "end": segment_end})
    return normalized


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
    segs = _normalize_segments(start, end, segments)
    try:
        focus_x = float(focus_x)
    except (TypeError, ValueError, OverflowError):
        focus_x = 0.5
    if not math.isfinite(focus_x):
        focus_x = 0.5
    focus_x = max(0.0, min(1.0, focus_x))
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
                timeout=1800,
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
                    timeout=1800,
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
                timeout=1800,
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
            timeout=1800,
        )
