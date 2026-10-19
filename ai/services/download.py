"""Download a supported public video URL to a private working directory."""

from __future__ import annotations

import os
import json
import math
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

SUPPORTED_HOSTS = {
    "youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be",
    "twitch.tv", "www.twitch.tv", "m.twitch.tv", "kick.com", "www.kick.com",
}
DOWNLOAD_TIMEOUT_SECONDS = 3 * 60 * 60
METADATA_TIMEOUT_SECONDS = 30
MIN_FREE_DISK_BYTES = int(os.getenv("MIN_FREE_DISK_BYTES", str(500 * 1024 * 1024)))


def check_disk_space(directory: Path, min_bytes: int = MIN_FREE_DISK_BYTES) -> None:
    """Verify sufficient free storage is available before starting heavy media downloads."""
    try:
        usage = shutil.disk_usage(directory)
        if usage.free < min_bytes:
            free_mb = usage.free // (1024 * 1024)
            req_mb = min_bytes // (1024 * 1024)
            raise RuntimeError(
                f"Insufficient disk space in {directory}: {free_mb}MB available, "
                f"requires at least {req_mb}MB."
            )
    except (OSError, ValueError):
        pass


def _cleanup_partials(directory: Path) -> None:
    """Safely delete incomplete or aborted download artifacts."""
    for pattern in ("*.part", "*.ytdl", "*.temp"):
        for file in directory.glob(pattern):
            try:
                if file.is_file():
                    file.unlink(missing_ok=True)
            except OSError:
                pass



def validate_video_url(url: str) -> str:
    """Return a normalized HTTP(S) URL from a supported video provider."""
    value = url.strip()
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme not in {"http", "https"} or not host:
        raise ValueError("Enter a valid HTTP or HTTPS video URL.")
    if parsed.username or parsed.password:
        raise ValueError("Video URLs must not contain embedded credentials.")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Video URL has an invalid port.") from exc
    if port not in {None, 80, 443}:
        raise ValueError("Video URLs must use the provider's standard web port.")
    if host not in SUPPORTED_HOSTS:
        raise ValueError(
            "Unsupported video provider. Supported providers are YouTube, Twitch, and Kick."
        )
    return value


def download(url: str, out_dir: str) -> str:
    """Download a single video, rejecting playlist expansion and partial outputs."""
    safe_url = validate_video_url(url)
    output_dir = Path(out_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    check_disk_space(output_dir)
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
        _cleanup_partials(output_dir)
        raise RuntimeError("Video download timed out after 3 hours.") from exc
    except FileNotFoundError as exc:
        raise RuntimeError("yt-dlp is not installed in the AI service environment.") from exc
    except Exception:
        _cleanup_partials(output_dir)
        raise

    if result.returncode != 0:
        _cleanup_partials(output_dir)
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


def get_video_metadata(url: str) -> dict:
    """Read provider metadata without downloading the source media."""
    safe_url = validate_video_url(url)
    try:
        result = subprocess.run(
            ["yt-dlp", "--ignore-config", "--no-playlist", "--no-warnings", "--dump-single-json", "--skip-download", safe_url],
            check=False,
            capture_output=True,
            text=True,
            timeout=METADATA_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Video metadata lookup timed out.") from exc
    except FileNotFoundError as exc:
        raise RuntimeError("yt-dlp is not installed in the AI service environment.") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        detail = detail[-1200:] if detail else "The source is private, deleted, or unavailable."
        raise RuntimeError(f"Video metadata lookup failed: {detail}")
    try:
        raw = json.loads(result.stdout)
    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("The provider returned invalid video metadata.") from exc
    try:
        duration = float(raw.get("duration"))
    except (TypeError, ValueError, OverflowError) as exc:
        raise RuntimeError("The provider did not return a usable video duration.") from exc
    if not math.isfinite(duration) or duration <= 0:
        raise RuntimeError("The provider did not return a usable video duration.")
    return {
        "title": str(raw.get("title") or "")[:300] or None,
        "duration": duration,
        "thumbnail": str(raw.get("thumbnail") or "")[:2048] or None,
        "platform": str(raw.get("extractor_key") or raw.get("extractor") or "Video")[:80],
        "sourceId": str(raw.get("id") or "")[:200] or None,
    }


def download_range(url: str, out_dir: str, start_seconds: float, end_seconds: float) -> str:
    """Ask yt-dlp/FFmpeg to retrieve only a provider time section; never fall back to a full download."""
    safe_url = validate_video_url(url)
    try:
        start, end = float(start_seconds), float(end_seconds)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Source range timestamps must be numeric.") from exc
    if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end <= start:
        raise ValueError("Source range must have finite non-negative timestamps with end after start.")
    output_dir = Path(out_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    check_disk_space(output_dir)
    template = str(output_dir / "source-range.%(ext)s")
    try:
        result = subprocess.run(
            [
                "yt-dlp", "--ignore-config", "--no-playlist", "--no-warnings", "--format", "bv*+ba/b",
                "--download-sections", f"*{start:.3f}-{end:.3f}",
                "--force-keyframes-at-cuts", "--downloader", "ffmpeg",
                "--merge-output-format", "mp4", "--output", template, safe_url,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=DOWNLOAD_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        _cleanup_partials(output_dir)
        raise RuntimeError("Selected source range download timed out.") from exc
    except FileNotFoundError as exc:
        raise RuntimeError("yt-dlp/FFmpeg is not installed in the AI service environment.") from exc
    except Exception:
        _cleanup_partials(output_dir)
        raise
    if result.returncode != 0:
        _cleanup_partials(output_dir)
        detail = (result.stderr or result.stdout or "").strip()
        detail = detail[-1200:] if detail else "The provider could not retrieve the selected section."
        raise RuntimeError(f"Selected source range download failed: {detail}")
    candidates = sorted(
        path for path in output_dir.glob("source-range.*")
        if path.is_file() and path.suffix.lower() not in {".part", ".ytdl", ".temp"} and path.stat().st_size > 0
    )
    if not candidates:
        raise RuntimeError("Range download completed without a media file; the worker will not analyze the full source.")
    return str(next((path for path in candidates if path.suffix.lower() == ".mp4"), candidates[0]))
