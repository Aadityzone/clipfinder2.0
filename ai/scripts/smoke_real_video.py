"""Run a real, authorized source URL through the AI service and verify a rendered clip.

This is an integration smoke test, not a mocked unit test. The AI service must have
yt-dlp, FFmpeg/FFprobe, transcription dependencies, and a writable media directory.
The supplied output directory must be a path on the AI service host/container.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def post_json(base_url: str, path: str, payload: dict, secret: str | None) -> dict:
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["x-ai-secret"] = secret
    request = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=3 * 60 * 60) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{path} returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach AI service at {base_url}: {exc.reason}") from exc
    if not isinstance(result, dict):
        raise RuntimeError(f"{path} returned an unexpected response type")
    return result


def run(base_url: str, source_url: str, output_dir: str, secret: str | None) -> dict:
    root = str(Path(output_dir).expanduser())
    Path(root).mkdir(parents=True, exist_ok=True)

    ingest = post_json(base_url, "/v1/ingest", {"url": source_url, "output_dir": root}, secret)
    source_path = ingest.get("media_path")
    metadata = ingest.get("metadata") or {}
    if not source_path or float(metadata.get("duration") or 0) <= 0:
        raise RuntimeError("Ingestion did not return a video path and positive duration")

    transcript = post_json(
        base_url, "/v1/transcribe", {"media_path": source_path}, secret
    )
    segments = transcript.get("segments")
    if not isinstance(segments, list):
        raise RuntimeError("Transcription did not return a timestamped segments list")

    analysis = post_json(
        base_url,
        "/v1/analyze",
        {
            "segments": segments,
            "instruction": "Find the strongest genuine clip-worthy moment; do not invent events.",
            "categories": ["AI Detect"],
            "media_path": source_path,
        },
        secret,
    )
    candidates = analysis.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise RuntimeError(
            "Analysis completed but produced no candidates; inspect media diagnostics before treating this as a successful pipeline run."
        )

    duration = float(metadata["duration"])
    valid = []
    for candidate in candidates:
        try:
            start = float(candidate["start"])
            end = float(candidate["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if 0 <= start < end <= duration + 0.05:
            valid.append((candidate, start, min(end, duration)))
    if not valid:
        raise RuntimeError("Analysis produced candidates, but none had valid source timestamps")

    candidate, start, end = max(valid, key=lambda item: float(item[0].get("score") or 0))
    output_path = str(Path(root) / "clipfinder-e2e-render.mp4")
    rendered = post_json(
        base_url,
        "/v1/render",
        {
            "input_path": source_path,
            "output_path": output_path,
            "start": start,
            "end": end,
            "segments": [{"start": start, "end": end}],
            "aspect": "9:16",
        },
        secret,
    )
    if not rendered.get("output_path") or int(rendered.get("size") or 0) < 1024:
        raise RuntimeError("Render endpoint did not confirm a non-empty output artifact")

    report = {
        "status": "passed",
        "source": {
            "duration_seconds": round(duration, 3),
            "width": metadata.get("width"),
            "height": metadata.get("height"),
            "codec": metadata.get("codec"),
            "has_audio": metadata.get("hasAudio"),
        },
        "transcription": {
            "language": transcript.get("language"),
            "segment_count": len(segments),
            "text_characters": len(str(transcript.get("text") or "")),
        },
        "analysis": {
            "candidate_count": len(candidates),
            "selected_candidate": {
                "start": round(start, 3),
                "end": round(end, 3),
                "score": candidate.get("score"),
                "category": candidate.get("category"),
                "rationale": candidate.get("rationale"),
            },
        },
        "render": {
            "path": rendered.get("output_path"),
            "size_bytes": rendered.get("size"),
            "duration_seconds": rendered.get("duration"),
            "width": rendered.get("width"),
            "height": rendered.get("height"),
        },
        "note": "AI-service pipeline verified. This script does not create web/Prisma jobs or verify the authenticated browser export path.",
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="Authorized video URL you have rights to process")
    parser.add_argument(
        "--output-dir",
        default=os.getenv("CLIPFINDER_E2E_OUTPUT_DIR", "/tmp/clipfinder-e2e"),
        help="Writable path on the AI service host/container",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("AI_SERVICE_URL", "http://127.0.0.1:8000"),
        help="AI service base URL",
    )
    args = parser.parse_args()
    try:
        report = run(args.base_url, args.url, args.output_dir, os.getenv("AI_SERVICE_SECRET"))
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2), file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
