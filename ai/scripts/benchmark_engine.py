"""Real-media progressive AI pipeline benchmark and E2E verification runner.

Generates real speech-containing test MP4 videos (via local TTS + FFmpeg with
varied energy bursts and visual scene cuts) or runs against an existing local
file / authorized URL, executes cold and warm progressive runs, and writes an
honest JSON benchmark report measuring milestones against the 2-3 min target.

Run from repository root:
  PYTHONPATH=. python ai/scripts/benchmark_engine.py --durations 180 900
  PYTHONPATH=. python ai/scripts/benchmark_engine.py --input path/to/video.mp4 --chunk-seconds 180
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import psutil

# Ensure repository root is importable when invoked directly as a script.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ai.services.download import download, download_range, get_video_metadata
from ai.services.media import ffprobe
from ai.services.progressive import run_progressive_pipeline
from ai.transcribe import model as get_whisper_model, transcription_capabilities


SPEECH_SCRIPTS = [
    (
        "Welcome back everyone to tonight's live strategy breakdown! "
        "Wait until you see what happens in the final seconds of this round. "
        "Notice how every single resource bar drops to zero right before the comeback play!"
    ),
    (
        "Here is the three-step architectural secret most engineers miss completely. "
        "First, stop buffering an entire hour in memory before extracting the first highlight. "
        "Second, overlap transcription with scoring! And third, render your highest ranked clip right now!"
    ),
    (
        "No way! Did you just see that last-second clutch deflection across the entire arena? "
        "Everybody in chat thought the match was already over, and then out of nowhere came the triple counter!"
    ),
    (
        "Let us slow down and explain why this market shift changes everything for creators this year. "
        "Retention in the first four seconds tripled once captions matched the exact punchline cadence."
    ),
    (
        "Watch closely right here: three big mistakes back to back, followed by an insane recovery. "
        "Always check your timestamps before cutting so you preserve the setup before the payoff!"
    ),
]


def _synthesize_base_clip(out_wav: Path, text: str) -> None:
    """Synthesize speech audio cleanly using Windows SAPI or espeak/FFmpeg fallback."""
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    if platform.system().lower() == "windows":
        ps_script = (
            "Add-Type -AssemblyName System.Speech; "
            "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$synth.Rate = 1; "
            f"$synth.SetOutputToWaveFile('{str(out_wav).replace(chr(39), chr(39)*2)}'); "
            f"$synth.Speak('{text.replace(chr(39), chr(39)*2)}'); "
            "$synth.Dispose()"
        )
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0 and out_wav.is_file() and out_wav.stat().st_size > 2048:
            return
    raise RuntimeError(f"Unable to synthesize real TTS speech WAV on {platform.system()}")


def generate_speech_video(target_mp4: Path, duration_s: int, work_dir: Path) -> Path:
    """Build a valid multi-scene MP4 containing real spoken English segments of `duration_s`."""
    if target_mp4.is_file():
        try:
            meta = ffprobe(str(target_mp4))
            if abs(float(meta.get("duration") or 0) - duration_s) <= 5.0 and meta.get("hasAudio"):
                return target_mp4
        except Exception:
            pass

    target_mp4.parent.mkdir(parents=True, exist_ok=True)
    seg_dir = work_dir / "_speech_segments"
    seg_dir.mkdir(parents=True, exist_ok=True)

    # Create 5 distinct spoken + visual scene segments (~25-35s each with pauses & volume peaks),
    # then concatenate and stream-copy up to target `duration_s` rapidly via FFmpeg.
    segment_files: list[Path] = []
    colors = ["0x1a2639", "0x2b193d", "0x1b4332", "0x4a1942", "0x102542"]
    for idx, script in enumerate(SPEECH_SCRIPTS):
        clip_mp4 = seg_dir / f"seg_{idx:02d}.mp4"
        if not clip_mp4.is_file() or clip_mp4.stat().st_size < 4096:
            wav_path = seg_dir / f"seg_{idx:02d}.wav"
            _synthesize_base_clip(wav_path, script)
            # Pad WAV with dynamic loudness swell + 4s trailing silence pause so pauses/energy boundaries exist
            proc = subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-f", "lavfi", "-i", f"testsrc2=size=1280x720:rate=24:duration=22",
                    "-f", "lavfi", "-i", f"color=c={colors[idx % len(colors)]}:size=1280x720:rate=24:duration=6",
                    "-i", str(wav_path),
                    "-filter_complex",
                    "[0:v][1:v]concat=n=2:v=1:a=0,format=yuv420p[v];"
                    "[2:a]aresample=48000,apad=whole_dur=28,volume='if(lt(t,6),1.35,if(lt(t,14),0.85,1.4))':eval=frame[a]",
                    "-map", "[v]", "-map", "[a]",
                    "-t", "28",
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28", "-g", "48",
                    "-c:a", "aac", "-b:a", "128k",
                    "-movflags", "+faststart",
                    str(clip_mp4),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode != 0 or not clip_mp4.is_file():
                raise RuntimeError(f"Failed generating speech test segment {idx}: {proc.stderr[-500:]}")
        segment_files.append(clip_mp4)

    concat_list = seg_dir / f"concat_{duration_s}.txt"
    total_written = 0.0
    lines: list[str] = []
    idx = 0
    while total_written < duration_s:
        seg = segment_files[idx % len(segment_files)]
        escaped = str(seg.resolve()).replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
        total_written += 28.0
        idx += 1
    concat_list.write_text("\n".join(lines), encoding="utf-8")

    proc = subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_list),
            "-t", str(duration_s),
            "-c", "copy",
            "-movflags", "+faststart",
            str(target_mp4),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0 or not target_mp4.is_file():
        raise RuntimeError(f"Failed assembling benchmark MP4 ({duration_s}s): {proc.stderr[-500:]}")
    return target_mp4


def _verify_clips(clips: list[dict[str, Any]]) -> list[dict[str, Any]]:
    verified: list[dict[str, Any]] = []
    for clip in clips:
        clip_path = Path(str(clip.get("path") or ""))
        if not clip_path.is_file():
            continue
        meta = ffprobe(str(clip_path))
        verified.append({
            "file": clip.get("file"),
            "score": clip.get("score"),
            "duration": clip.get("duration"),
            "verifiedDuration": meta.get("duration"),
            "width": meta.get("width"),
            "height": meta.get("height"),
            "hasAudio": meta.get("hasAudio"),
            "bytes": clip_path.stat().st_size,
            "renderSeconds": clip.get("renderSeconds"),
        })
    return verified


def run_single_benchmark(
    source_path: Path,
    out_dir: Path,
    *,
    label: str,
    chunk_seconds: float,
    top: int,
    transcribe_concurrency: int | None,
    render_concurrency: int | None,
    ingestion_metrics: dict[str, Any] | None = None,
    warmup: bool = False,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in [out_dir / "checkpoint.json", out_dir / "report.json", out_dir / "transcript.json", *out_dir.glob("clip-*.mp4")]:
        stale.unlink(missing_ok=True)

    print(f"[benchmark] starting {label} ({source_path.name}, chunk={chunk_seconds}s)", file=sys.stderr, flush=True)
    warmup_seconds = 0.0
    if warmup:
        t0 = time.perf_counter()
        get_whisper_model()
        warmup_seconds = round(time.perf_counter() - t0, 3)

    report = run_progressive_pipeline(
        source_path,
        out_dir,
        top=top,
        chunk_duration_s=chunk_seconds,
        transcribe_concurrency=transcribe_concurrency,
        render_concurrency=render_concurrency,
        checkpoint_path=out_dir / "checkpoint.json",
        ingestion_metrics=ingestion_metrics,
        source_label=str(source_path),
    )
    print(
        f"[benchmark] finished {label}: first={report['milestones'].get('firstPlayableClipSeconds')}s "
        f"third={report['milestones'].get('thirdPlayableClipSeconds')}s "
        f"total={report['milestones'].get('totalPipelineSeconds')}s",
        file=sys.stderr,
        flush=True,
    )

    verified = _verify_clips(report.get("clips") or [])
    third_s = report["milestones"].get("thirdPlayableClipSeconds")
    first_s = report["milestones"].get("firstPlayableClipSeconds")
    target_met = third_s is not None and third_s <= 180.0

    return {
        "label": label,
        "warmupUsed": warmup,
        "warmupSeconds": warmup_seconds,
        "chunkSeconds": chunk_seconds,
        "status": report.get("status"),
        "mediaDurationSeconds": report["media"].get("duration"),
        "sourceBytes": report["media"].get("sourceBytes"),
        "milestones": report.get("milestones"),
        "performance": report.get("performance"),
        "transcription": report.get("transcription"),
        "analysis": report.get("analysis"),
        "verifiedPlayableClips": verified,
        "targetEvaluation": {
            "targetFirst3ClipsSeconds": 180.0,
            "firstPlayableClipSeconds": first_s,
            "thirdPlayableClipSeconds": third_s,
            "metTargetWithin180s": target_met,
        },
    }


def _run_cold_subprocess(
    source_path: Path,
    out_dir: Path,
    *,
    chunk_seconds: float,
    top: int,
) -> dict[str, Any]:
    """Run one isolated Python process so Whisper model load time is truly cold."""
    env = dict(os.environ)
    env.setdefault("WHISPER_LOCAL_FILES_ONLY", "1")
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--input",
        str(source_path),
        "--output-dir",
        str(out_dir),
        "--chunk-seconds",
        str(chunk_seconds),
        "--top",
        str(top),
        "--single-run",
        "--label",
        f"cold_{source_path.stem}",
    ]
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"Cold subprocess failed (exit {proc.returncode}): {proc.stderr[-800:]}")
    summary_file = out_dir / "benchmark_single.json"
    return json.loads(summary_file.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Clip Finder 2.0 progressive AI engine.")
    parser.add_argument("--input", help="Existing local video file to benchmark")
    parser.add_argument("--url", help="Authorized video URL to download (range or full) and benchmark")
    parser.add_argument("--start-seconds", type=float, default=None, help="Optional range start for --url")
    parser.add_argument("--end-seconds", type=float, default=None, help="Optional range end for --url")
    parser.add_argument(
        "--durations",
        nargs="*",
        type=int,
        default=[180, 900],
        help="Synthetic real-speech MP4 durations in seconds to generate & benchmark (default: 180 900)",
    )
    parser.add_argument("--chunk-seconds", type=float, default=120.0, help="Progressive chunk size (seconds)")
    parser.add_argument("--top", type=int, default=3, help="Target top playable clips")
    parser.add_argument("--transcribe-concurrency", type=int, default=None)
    parser.add_argument("--render-concurrency", type=int, default=None)
    parser.add_argument("--include-cold", action="store_true", help="Also run a cold-start subprocess on first video")
    parser.add_argument("--single-run", action="store_true", help="Internal single-process run mode")
    parser.add_argument("--label", default="custom", help="Run label for single-run mode")
    parser.add_argument(
        "--output-dir",
        default=str(REPO_ROOT / "artifacts" / "benchmark-engine"),
        help="Directory for benchmark media and JSON reports",
    )
    args = parser.parse_args()

    out_root = Path(args.output_dir).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("WHISPER_LOCAL_FILES_ONLY", "1")

    if args.single_run:
        if not args.input:
            raise SystemExit("--single-run requires --input")
        result = run_single_benchmark(
            Path(args.input).resolve(),
            out_root,
            label=args.label,
            chunk_seconds=args.chunk_seconds,
            top=args.top,
            transcribe_concurrency=args.transcribe_concurrency,
            render_concurrency=args.render_concurrency,
            warmup=False,
        )
        (out_root / "benchmark_single.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
        return

    runs: list[dict[str, Any]] = []

    if args.url:
        ingest_dir = out_root / "url_ingest"
        ingest_dir.mkdir(parents=True, exist_ok=True)
        m0 = time.perf_counter()
        meta = get_video_metadata(args.url)
        meta_s = round(time.perf_counter() - m0, 3)

        d0 = time.perf_counter()
        if args.start_seconds is not None and args.end_seconds is not None:
            downloaded = Path(download_range(args.url, str(ingest_dir), args.start_seconds, args.end_seconds))
        else:
            downloaded = Path(download(args.url, str(ingest_dir)))
        dl_s = round(time.perf_counter() - d0, 3)

        runs.append(
            run_single_benchmark(
                downloaded,
                out_root / "url_run",
                label="url_progressive",
                chunk_seconds=args.chunk_seconds,
                top=args.top,
                transcribe_concurrency=args.transcribe_concurrency,
                render_concurrency=args.render_concurrency,
                ingestion_metrics={
                    "metadataLookupSeconds": meta_s,
                    "sourceDownloadSeconds": dl_s,
                    "sourceBytesDownloaded": downloaded.stat().st_size,
                },
                warmup=True,
            )
        )
    elif args.input:
        src = Path(args.input).resolve()
        if args.include_cold:
            runs.append(_run_cold_subprocess(src, out_root / "cold", chunk_seconds=args.chunk_seconds, top=args.top))
        runs.append(
            run_single_benchmark(
                src,
                out_root / "warm",
                label=f"warm_{src.stem}",
                chunk_seconds=args.chunk_seconds,
                top=args.top,
                transcribe_concurrency=args.transcribe_concurrency,
                render_concurrency=args.render_concurrency,
                warmup=True,
            )
        )
    else:
        fixtures_dir = out_root / "fixtures"
        for idx, dur in enumerate(args.durations):
            mp4 = generate_speech_video(fixtures_dir / f"speech_{dur}s.mp4", dur, fixtures_dir)
            if idx == 0 and args.include_cold:
                runs.append(
                    _run_cold_subprocess(
                        mp4,
                        out_root / f"run_{dur}s_cold",
                        chunk_seconds=args.chunk_seconds,
                        top=args.top,
                    )
                )
            runs.append(
                run_single_benchmark(
                    mp4,
                    out_root / f"run_{dur}s_warm",
                    label=f"warm_{dur}s",
                    chunk_seconds=args.chunk_seconds,
                    top=args.top,
                    transcribe_concurrency=args.transcribe_concurrency,
                    render_concurrency=args.render_concurrency,
                    warmup=(idx == 0),
                )
            )

    summary = {
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "hardware": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "logicalCpus": os.cpu_count(),
            "totalRamGb": round(psutil.virtual_memory().total / (1024 ** 3), 2),
            "whisperModel": os.getenv("WHISPER_MODEL", "small"),
        },
        "capabilitiesAfterRun": transcription_capabilities(),
        "runs": runs,
    }
    report_path = out_root / "benchmark_summary.json"
    report_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

