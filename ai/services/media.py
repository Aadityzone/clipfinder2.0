import json
import subprocess


def ffprobe(path: str, timeout: float = 60.0) -> dict:
    try:
        raw = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path],
            text=True,
            timeout=timeout,
        )
        data = json.loads(raw)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"ffprobe timed out after {timeout} seconds on {path}") from exc
    except (subprocess.CalledProcessError, OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"ffprobe failed for {path}: {exc}") from exc

    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    fps = None
    if video and "/" in str(video.get("r_frame_rate", "")):
        a, b = video["r_frame_rate"].split("/", 1)
        fps = float(a) / float(b) if float(b) else None
    return {
        "duration": float(data.get("format", {}).get("duration") or 0),
        "width": video.get("width") if video else None,
        "height": video.get("height") if video else None,
        "fps": fps,
        "codec": video.get("codec_name") if video else None,
        "hasAudio": audio is not None,
    }