"""Timestamp-preserving frame sampling and scene context for video analysis.

FFmpeg performs sparse decoding and reports presentation timestamps for the
frames it actually emits. The default path makes no semantic claims about a
frame; it packages measured scene, motion, face and OCR evidence for consumers.
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

_PTS = re.compile(r"n:\s*(\d+).*?pts_time:([+-]?(?:\d+(?:\.\d*)?|\.\d+))")


def _positive_float(value: Any, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return number if math.isfinite(number) and number > 0 else default


def video_stream_info(path: str, timeout_s: float = 30.0) -> dict:
    """Read the selected video stream time base and offsets using ffprobe."""
    try:
        raw = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=index,codec_type,width,height,avg_frame_rate,r_frame_rate,time_base,start_time,duration,nb_frames",
             "-show_entries", "format=start_time,duration", "-of", "json", path],
            check=True, capture_output=True, text=True, timeout=timeout_s,
        ).stdout
        result = json.loads(raw)
        streams = result.get("streams") or []
        if not streams:
            return {"available": False, "reason": "no video stream"}
        stream = streams[0]
        return {
            "available": True,
            "streamIndex": stream.get("index"),
            "width": stream.get("width"),
            "height": stream.get("height"),
            "avgFrameRate": stream.get("avg_frame_rate"),
            "realFrameRate": stream.get("r_frame_rate"),
            "timeBase": stream.get("time_base"),
            "streamStartS": _finite(stream.get("start_time")),
            "containerStartS": _finite((result.get("format") or {}).get("start_time")),
            "durationS": _finite(stream.get("duration")) or _finite((result.get("format") or {}).get("duration")),
            "frameCount": _int_or_none(stream.get("nb_frames")),
        }
    except FileNotFoundError:
        return {"available": False, "reason": "ffprobe executable is unavailable"}
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        return {"available": False, "reason": f"ffprobe failed ({type(exc).__name__})"}


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


def extract_sampled_frames(
    path: str,
    *,
    interval_s: float | None = None,
    max_frames: int | None = None,
    max_width: int | None = None,
    timeout_s: float = 600.0,
) -> dict:
    """Extract sparse JPEG frames in a temporary directory, keyed by source PTS.

    Returned records contain timestamp references, not temporary file paths.
    FFmpeg's `fps` filter drops duplicate timestamps and caps the cadence for
    VFR/CFR inputs alike. Temporary image files are removed on every outcome.
    Limits and sampling settings are environment-configurable.
    """
    if not os.path.isfile(path):
        return {"available": False, "frames": [], "reason": "media not found"}
    if not shutil.which("ffmpeg"):
        return {"available": False, "frames": [], "reason": "ffmpeg executable is unavailable"}
    interval = _positive_float(interval_s if interval_s is not None else os.getenv("VISUAL_SAMPLE_INTERVAL_S"), 2.0)
    try:
        limit = int(max_frames if max_frames is not None else os.getenv("VISUAL_MAX_FRAMES", "180"))
    except (TypeError, ValueError, OverflowError):
        limit = 180
    limit = max(1, min(2000, limit))
    try:
        width = int(max_width if max_width is not None else os.getenv("VISUAL_MAX_FRAME_WIDTH", "640"))
    except (TypeError, ValueError, OverflowError):
        width = 640
    width = max(160, min(1920, width))
    info = video_stream_info(path)
    if not info.get("available"):
        return {"available": False, "frames": [], "reason": info.get("reason"), "stream": info}

    with tempfile.TemporaryDirectory(prefix="clipfinder-frames-") as directory:
        pattern = str(Path(directory) / "%06d.jpg")
        vf = f"fps=1/{interval:.6f},scale=w='min({width},iw)':h=-2:force_original_aspect_ratio=decrease,showinfo"
        command = ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "info", "-i", path,
                   "-map", "0:v:0", "-an", "-sn", "-dn", "-vf", vf,
                   "-frames:v", str(limit), "-q:v", "4", "-f", "image2", pattern]
        try:
            proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout_s)
        except subprocess.TimeoutExpired:
            return {"available": False, "frames": [], "reason": f"frame extraction timed out after {timeout_s:g}s", "stream": info}
        except OSError as exc:
            return {"available": False, "frames": [], "reason": f"frame extraction failed ({type(exc).__name__})", "stream": info}
        if proc.returncode != 0:
            return {"available": False, "frames": [], "reason": "ffmpeg frame extraction failed", "stream": info}

        pts_by_index: dict[int, float] = {}
        for match in _PTS.finditer(proc.stderr):
            index, timestamp = int(match.group(1)), float(match.group(2))
            if math.isfinite(timestamp):
                pts_by_index[index] = timestamp
        files = sorted(Path(directory).glob("*.jpg"))
        frames = []
        visual_samples = []
        previous_pts = None
        previous_image = None
        previous_signature = None
        for index, file_path in enumerate(files):
            timestamp = pts_by_index.get(index)
            if timestamp is None:
                continue
            # Protect downstream windows from duplicate output caused by unusual
            # timestamp streams while retaining the first exact presentation PTS.
            if previous_pts is not None and timestamp <= previous_pts + 1e-6:
                continue
            previous_pts = timestamp
            frame_row = {
                "frameIndex": index,
                "timestampS": round(timestamp, 6),
                "frameRef": {"type": "source_timestamp", "timestampS": round(timestamp, 6)},
                "width": None,
                "height": None,
                "sampleIntervalS": interval,
                "imageBytes": file_path.stat().st_size,
            }
            frames.append(frame_row)
            try:
                import cv2
                import numpy as np
                image = cv2.imread(str(file_path))
                if image is not None:
                    frame_row["height"], frame_row["width"] = image.shape[:2]
                    small = cv2.resize(image, (64, 36))
                    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
                    hist = cv2.calcHist([hsv], [0, 1], None, [16, 8], [0, 180, 0, 256])
                    signature = cv2.normalize(hist, hist).flatten()
                    visual_change = (
                        float(min(1.0, np.mean(np.abs(signature - previous_signature)) * 3.0))
                        if previous_signature is not None else 0.0
                    )
                    motion = 0.0
                    if previous_image is not None:
                        a = cv2.resize(previous_image, (160, 90))
                        b = cv2.resize(image, (160, 90))
                        flow = cv2.calcOpticalFlowFarneback(
                            cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), cv2.cvtColor(b, cv2.COLOR_BGR2GRAY),
                            None, 0.5, 3, 15, 3, 5, 1.2, 0,
                        )
                        magnitude = np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)
                        motion = float(min(1.0, np.percentile(magnitude, 75) / 8.0))
                    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                    height, width_pixels = gray.shape
                    center = gray[int(height * .2):int(height * .8), int(width_pixels * .2):int(width_pixels * .8)]
                    center_detail = float(cv2.Laplacian(center, cv2.CV_64F).var())
                    visual_samples.append({
                        "time": round(timestamp, 3),
                        "visualChange": round(visual_change, 4),
                        "motion": round(motion, 4),
                        "brightness": round(float(np.mean(gray) / 255.0), 4),
                        "centerDetail": round(min(1.0, center_detail / 1200.0), 4),
                    })
                    previous_image = image
                    previous_signature = signature
            except Exception:
                # Frame references remain usable even when optional OpenCV
                # measurements are unavailable or fail for one sampled image.
                pass
        return {
            "available": True,
            "sampling": "ffmpeg_fps_filter",
            "sampleIntervalS": interval,
            "frameLimit": limit,
            "frameCount": len(frames),
            "durationS": info.get("durationS"),
            "stream": info,
            "frames": frames,
            "visualSamples": visual_samples,
        }


def build_visual_context(
    frames: dict,
    *,
    scenes: dict | None = None,
    visual_samples: dict | None = None,
    on_screen: dict | None = None,
    vision: dict | None = None,
    audio_windows: list[dict] | None = None,
    transcript_segments: list[dict] | None = None,
) -> dict:
    """Join observed signals into timestamped scene records without guessing semantics."""
    if not isinstance(frames, dict) or not frames.get("available"):
        return {"available": False, "scenes": [], "reason": (frames or {}).get("reason", "frame analysis unavailable")}
    scene_times = (scenes or {}).get("sceneChanges", []) if isinstance(scenes, dict) else []
    boundaries = sorted({t for value in scene_times if (t := _finite(value)) is not None and t > 0})
    frame_rows = [row for row in frames.get("frames", []) if isinstance(row, dict)]
    visual_rows = (visual_samples or {}).get("samples", []) if isinstance(visual_samples, dict) else []
    screen_rows = (on_screen or {}).get("samples", []) if isinstance(on_screen, dict) else []
    face_rows = (vision or {}).get("faces", []) if isinstance(vision, dict) else []
    audio = audio_windows or []
    transcript = transcript_segments or []
    duration = _finite(frames.get("durationS")) or 0.0
    starts = [0.0, *(value for value in boundaries if duration <= 0 or value < duration)]
    ends = [*starts[1:], duration if duration > 0 else float("inf")]

    def at(row: Any) -> float | None:
        if not isinstance(row, dict):
            return None
        return _finite(row.get("timestampS", row.get("time", row.get("start"))))

    records = []
    for start, end in zip(starts, ends):
        scene_frames = [row for row in frame_rows if start <= (at(row) or 0) < end]
        scene_visual = [row for row in visual_rows if isinstance(row, dict) and start <= (at(row) or -1) < end]
        scene_screen = [row for row in screen_rows if isinstance(row, dict) and start <= (at(row) or -1) < end]
        scene_faces = [row for row in face_rows if isinstance(row, dict) and start <= (at(row) or -1) < end]
        scene_audio = [row for row in audio if isinstance(row, dict) and (_finite(row.get("end")) or -1) > start and (_finite(row.get("start")) or float("inf")) < end]
        scene_transcript = [row for row in transcript if isinstance(row, dict) and (_finite(row.get("end")) or -1) > start and (_finite(row.get("start")) or float("inf")) < end]
        changes = [row for row in scene_visual if _finite(row.get("visualChange")) is not None]
        records.append({
            "startS": round(start, 3),
            "endS": round(end, 3) if math.isfinite(end) else None,
            "boundaryAtStart": start in boundaries,
            "frameReferences": [row.get("frameRef") for row in scene_frames if row.get("frameRef")],
            "visualEvidence": {
                "sampleCount": len(scene_visual),
                "meanMotion": round(sum(_finite(row.get("motion")) or 0 for row in scene_visual) / len(scene_visual), 4) if scene_visual else None,
                "maxVisualChange": round(max((_finite(row.get("visualChange")) or 0 for row in changes), default=0), 4) if changes else None,
                "faceSampleCount": len(scene_faces),
            },
            "onScreenText": [str(row.get("ocrText"))[:500] for row in scene_screen if row.get("ocrText")],
            "audioEvidence": {"windowCount": len(scene_audio), "speakerIds": sorted({str(row.get("speakerId")) for row in scene_transcript if row.get("speakerId")})},
            "transcriptContext": [
                {"startS": _finite(row.get("start")), "endS": _finite(row.get("end")), "text": str(row.get("text", ""))[:500]}
                for row in scene_transcript if row.get("text")
            ][:20],
            "semanticDescription": None,
        })
    return {
        "available": True,
        "timestampBasis": "ffmpeg_video_presentation_timestamp_seconds",
        "sceneCount": len(records),
        "scenes": records[:1000],
    }
