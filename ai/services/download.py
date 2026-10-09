"""Download a supported public video URL to a private working directory."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from urllib.parse import urlparse

SUPPORTED_HOSTS = (
    "youtube.com",
    "youtu.be",
    "twitch.tv",
    "kick.com",
)
DOWNLOAD_TIMEOUT_SECONDS = 3 * 60 * 60


def validate_video_url(url: str) -> str:
    """Return a normalized HTTP(S) URL from a supported video provider."""
    value = url.strip()
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme not in {"http", "https"} or not host:
        raise ValueError("Enter a valid HTTP or HTTPS video URL.")
    if parsed.username or parsed.password:
        raise ValueError("Video URLs must not contain embedded credentials.")
    if not any(host == allowed or host.endswith("." + allowed) for allowed in SUPPORTED_HOSTS):
        raise ValueError(
            "Unsupported video provider. Supported providers are YouTube, Twitch, and Kick."
        )
    return value


def download(url: str, out_dir: str) -> str:
    """Download a single video, rejecting playlist expansion and partial outputs."""
    safe_url = validate_video_url(url)
    output_dir = Path(out_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    template = str(output_dir / "source.%(ext)s")

    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "--no-playlist",
                "--no-warnings",
                "--format",
                "bv*+ba/b",
                "--merge-output-format",
                "mp4",
                "--output",
                template,
                safe_url,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=DOWNLOAD_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Video download timed out after 3 hours.") from exc
    except FileNotFoundError as exc:
        raise RuntimeError("yt-dlp is not installed in the AI service environment.") from exc

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        # Keep provider output useful for debugging without returning huge logs.
        detail = detail[-1200:] if detail else "yt-dlp exited without an error message."
        raise RuntimeError(f"Video download failed: {detail}")

    candidates = sorted(
        path
        for path in output_dir.glob("source.*")
        if path.is_file()
        and path.suffix.lower() not in {".part", ".ytdl", ".temp"}
        and path.stat().st_size > 0
    )
    if not candidates:
        raise RuntimeError("yt-dlp finished but produced no complete media file.")

    # Prefer the requested merged MP4, otherwise accept the completed source format.
    mp4 = next((path for path in candidates if path.suffix.lower() == ".mp4"), None)
    return str(mp4 or candidates[0])
