"""Download a supported public video URL to a private working directory."""

from __future__ import annotations

import ipaddress
import json
import math
import os
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

# Supported video hostnames
SUPPORTED_HOSTS = {
    "youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be",
    "twitch.tv", "www.twitch.tv", "m.twitch.tv", "clips.twitch.tv",
    "kick.com", "www.kick.com",
}

# Direct public video extensions supported via generic acquisition
DIRECT_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".mkv", ".m4v"}

DOWNLOAD_TIMEOUT_SECONDS = 3 * 60 * 60
METADATA_TIMEOUT_SECONDS = 30
MIN_FREE_DISK_BYTES = int(os.getenv("MIN_FREE_DISK_BYTES", str(500 * 1024 * 1024)))
MAX_DOWNLOAD_SIZE_BYTES = int(os.getenv("MAX_DOWNLOAD_SIZE_BYTES", str(15 * 1024 * 1024 * 1024)))  # 15GB default
MAX_RETRIES = int(os.getenv("DOWNLOAD_MAX_RETRIES", "2"))


# --- Error Hierarchy ---

class SourceAcquisitionError(RuntimeError):
    """Base error for all media acquisition failures."""
    pass


class UnsupportedSourceError(ValueError):
    """Raised when URL provider or scheme is not supported."""
    pass


class PrivateOrDeletedVideoError(SourceAcquisitionError):
    """Raised when source video is private, removed, deleted, or 404."""
    pass


class RestrictedVideoError(SourceAcquisitionError):
    """Raised when source video has DRM, age gate, login wall, or geo-block."""
    pass


class TransientNetworkError(SourceAcquisitionError):
    """Raised on recoverable network drops, timeouts, or transient 5xx faults."""
    pass


class StorageLimitError(SourceAcquisitionError):
    """Raised when available disk storage is below safety threshold."""
    pass


class CorruptedDownloadError(SourceAcquisitionError):
    """Raised when downloaded file is incomplete, empty, or unparseable."""
    pass


def classify_acquisition_error(error_text: str) -> SourceAcquisitionError:
    """Classify provider error output into typed acquisition exceptions."""
    text = (error_text or "").lower()

    # Private, deleted, or not found
    if any(p in text for p in [
        "private video", "this video is private", "removed by the uploader",
        "video unavailable", "not available", "does not exist", "deleted",
        "404", "not found", "vod unavailable", "no video formats found"
    ]):
        return PrivateOrDeletedVideoError(f"Source video is unavailable or deleted: {error_text}")

    # Restricted, age-gated, geo-blocked, login required, DRM
    if any(p in text for p in [
        "sign in to confirm", "confirm your age", "age-restricted", "members-only",
        "login required", "geo-restricted", "not available in your country",
        "drm protected", "copyright claim", "requires payment"
    ]):
        return RestrictedVideoError(f"Source video is restricted or access-controlled: {error_text}")

    # Transient network errors
    if any(p in text for p in [
        "timed out", "timeout", "connection reset", "connection refused",
        "temporary failure in name resolution", "name or service not known",
        "network is unreachable", "http error 5", "502 bad gateway",
        "503 service unavailable", "504 gateway timeout", "unable to download webpage"
    ]):
        return TransientNetworkError(f"Transient network error during acquisition: {error_text}")

    # Fallback to generic acquisition error preserving provider detail
    return SourceAcquisitionError(f"Video acquisition failed: {error_text}")


def check_disk_space(directory: Path, min_bytes: int = MIN_FREE_DISK_BYTES) -> None:
    """Verify sufficient free storage is available before starting heavy media downloads."""
    try:
        usage = shutil.disk_usage(directory)
        if usage.free < min_bytes:
            free_mb = usage.free // (1024 * 1024)
            req_mb = min_bytes // (1024 * 1024)
            raise StorageLimitError(
                f"Insufficient disk space in {directory}: {free_mb}MB available, "
                f"requires at least {req_mb}MB."
            )
    except OSError:
        pass


def _cleanup_partials(directory: Path) -> None:
    """Safely delete incomplete or aborted download artifacts."""
    for pattern in ("*.part", "*.ytdl", "*.temp", "source-range.*.part"):
        for file in directory.glob(pattern):
            try:
                if file.is_file():
                    file.unlink(missing_ok=True)
            except OSError:
                pass


def is_safe_public_ip(host: str) -> bool:
    """Return False if host resolves or parses to a loopback, private, or multicast IP."""
    if host in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}:
        return False
    try:
        ip = ipaddress.ip_address(host)
        return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified)
    except ValueError:
        return True


def validate_video_url(url: str) -> str:
    """Return a normalized HTTP(S) URL from a supported video provider or direct media URL."""
    value = url.strip()
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme not in {"http", "https"} or not host:
        raise ValueError("Enter a valid HTTP or HTTPS video URL.")
    if parsed.username or parsed.password:
        raise ValueError("Video URLs must not contain embedded credentials.")
    if not is_safe_public_ip(host):
        raise ValueError("Video URLs pointing to local or private networks are forbidden.")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Video URL has an invalid port.") from exc
    if port not in {None, 80, 443}:
        raise ValueError("Video URLs must use the provider's standard web port.")

    # Check supported providers
    if host in SUPPORTED_HOSTS:
        return value

    # Check direct media URL with standard video extension
    path_lower = parsed.path.lower()
    if any(path_lower.endswith(ext) for ext in DIRECT_VIDEO_EXTENSIONS):
        return value

    raise ValueError(
        "Unsupported video provider. Supported providers are YouTube, Twitch, Kick, and direct public media files."
    )


def download(url: str, out_dir: str) -> str:
    """Download a single video, rejecting playlist expansion and partial outputs, with bounded retries."""
    safe_url = validate_video_url(url)
    output_dir = Path(out_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    check_disk_space(output_dir)
    template = str(output_dir / "source.%(ext)s")

    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--no-warnings",
        "--continue",
        "--max-filesize", str(MAX_DOWNLOAD_SIZE_BYTES),
        "--format", "bv*+ba/b",
        "--merge-output-format", "mp4",
        "--output", template,
        safe_url,
    ]

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            result = subprocess.run(
                cmd,
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
        except Exception as exc:
            _cleanup_partials(output_dir)
            raise exc

        if result.returncode == 0:
            break

        _cleanup_partials(output_dir)
        detail = (result.stderr or result.stdout or "").strip()
        detail = detail[-1200:] if detail else "yt-dlp exited without an error message."
        classified = classify_acquisition_error(detail)
        last_error = classified

        # Only retry transient network errors
        if isinstance(classified, TransientNetworkError) and attempt < MAX_RETRIES:
            time.sleep(1.0 * (attempt + 1))
            continue
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
        classified = classify_acquisition_error(detail)
        if isinstance(classified, (PrivateOrDeletedVideoError, RestrictedVideoError)):
            raise classified
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
        "width": raw.get("width"),
        "height": raw.get("height"),
        "fps": raw.get("fps"),
        "vcodec": raw.get("vcodec"),
        "acodec": raw.get("acodec"),
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

    cmd = [
        "yt-dlp", "--ignore-config", "--no-playlist", "--no-warnings", "--format", "bv*+ba/b",
        "--download-sections", f"*{start:.3f}-{end:.3f}",
        "--force-keyframes-at-cuts", "--downloader", "ffmpeg",
        "--merge-output-format", "mp4", "--output", template, safe_url,
    ]

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            result = subprocess.run(
                cmd,
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
        except Exception as exc:
            _cleanup_partials(output_dir)
            raise exc

        if result.returncode == 0:
            break

        _cleanup_partials(output_dir)
        detail = (result.stderr or result.stdout or "").strip()
        detail = detail[-1200:] if detail else "The provider could not retrieve the selected section."
        classified = classify_acquisition_error(detail)
        last_error = classified

        if isinstance(classified, TransientNetworkError) and attempt < MAX_RETRIES:
            time.sleep(1.0 * (attempt + 1))
            continue
        raise RuntimeError(f"Selected source range download failed: {detail}")

    candidates = sorted(
        path for path in output_dir.glob("source-range.*")
        if path.is_file() and path.suffix.lower() not in {".part", ".ytdl", ".temp"} and path.stat().st_size > 0
    )
    if not candidates:
        raise RuntimeError("Range download completed without a media file; the worker will not analyze the full source.")
    return str(next((path for path in candidates if path.suffix.lower() == ".mp4"), candidates[0]))
