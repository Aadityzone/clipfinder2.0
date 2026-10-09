import os
import subprocess
import tempfile

from .captions import write_ass


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

    def render_base(base_output: str):
        if len(segs) == 1:
            segment = segs[0]
            duration = max(0.01, float(segment["end"]) - float(segment["start"]))
            subprocess.run(
                [
                    "ffmpeg", "-y", "-ss", str(segment["start"]), "-i", input_path,
                    "-t", str(duration), "-vf", vf, "-c:v", "libx264",
                    "-preset", "veryfast", "-crf", "20", "-af",
                    "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:a", "aac",
                    "-movflags", "+faststart", base_output,
                ],
                check=True,
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
                        "-t", str(duration), "-vf", vf, "-c:v", "libx264",
                        "-preset", "veryfast", "-crf", "20", "-af",
                        "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:a", "aac",
                        "-movflags", "+faststart", part_path,
                    ],
                    check=True,
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
        )
