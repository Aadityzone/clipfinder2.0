import json
import threading
import time
from pathlib import Path

import pytest

from ai.services import download as download_service
from ai.services import progressive
from ai.services.transcription_chunking import (
    deduplicate_boundary_words,
    plan_chunk_windows,
    transcribe_single_chunk,
)


def _make_dummy_source(path: Path) -> Path:
    path.write_bytes(b"\x00" * 4096)
    return path


def _fake_render_writer(out_path: str, size: int = 2048):
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"ftypmp42" + b"\x00" * max(0, size - 8))


def test_merge_progressive_candidates_refines_unrendered_and_skips_rendered():
    existing = [
        {"start": 10.0, "end": 30.0, "score": 0.90, "title": "Locked top clip", "_rendered": True},
        {"start": 80.0, "end": 105.0, "score": 0.72, "title": "Old draft"},
    ]
    incoming = [
        # Overlaps locked rendered clip with even higher score -> must NOT duplicate or replace
        {"start": 11.0, "end": 29.0, "score": 0.99, "title": "Should be ignored"},
        # Overlaps unrendered clip with higher score -> should refine in-place
        {"start": 79.0, "end": 106.0, "score": 0.88, "title": "Refined better hook"},
        # Overlaps unrendered clip with lower score -> should keep better one
        {"start": 81.0, "end": 104.0, "score": 0.50, "title": "Weaker overlap"},
        # Distinct new clip
        {"start": 140.0, "end": 165.0, "score": 0.81, "title": "Distinct winner"},
    ]

    merged = progressive.merge_progressive_candidates(
        existing,
        incoming,
        rendered_spans=[(10.0, 30.0)],
        iou_threshold=0.45,
    )

    titles = [item["title"] for item in merged]
    assert "Locked top clip" in titles
    assert "Should be ignored" not in titles
    assert "Refined better hook" in titles
    assert "Old draft" not in titles
    assert "Distinct winner" in titles
    assert len(merged) == 3
    assert [item["score"] for item in merged] == sorted([item["score"] for item in merged], reverse=True)


def test_progressive_checkpoint_persistence_and_resume(tmp_path: Path, monkeypatch):
    source = _make_dummy_source(tmp_path / "source.mp4")
    out_dir = tmp_path / "out"
    checkpoint = tmp_path / "checkpoint.json"

    monkeypatch.setattr(
        progressive,
        "ffprobe",
        lambda path, strict=True: {
            "duration": 240.0 if str(path) == str(source) else 20.0,
            "width": 1920 if str(path) == str(source) else 1080,
            "height": 1080 if str(path) == str(source) else 1920,
            "hasAudio": True,
            "format": "mp4",
        },
    )

    # Pre-seed checkpoint with chunk 0 already transcribed
    checkpoint.write_text(
        json.dumps(
            {
                "source": str(source),
                "completedChunks": [
                    {
                        "index": 0,
                        "start_time": 0.0,
                        "end_time": 120.0,
                        "language": "en",
                        "segments": [
                            {"start": 10.0, "end": 25.0, "text": "Chunk zero hook"},
                        ],
                    }
                ],
                "candidates": [
                    {"start": 10.0, "end": 30.0, "score": 0.91, "title": "Resumed chunk zero clip"}
                ],
            }
        ),
        encoding="utf-8",
    )

    transcribed_indices: list[int] = []

    def fake_transcribe_single_chunk(win, **kwargs):
        transcribed_indices.append(win["index"])
        return {
            "index": win["index"],
            "start_time": win["start_time"],
            "end_time": win["end_time"],
            "language": "en",
            "segments": [
                {"start": win["start_time"] + 15.0, "end": win["start_time"] + 30.0, "text": "Chunk one payoff"},
            ],
        }

    def fake_analyze(req):
        return {
            "candidates": [
                {"start": 135.0, "end": 160.0, "score": 0.85, "title": "Chunk one highlight"}
            ]
        }

    rendered_titles: list[tuple[float, float]] = []

    def fake_render(src, dst, **kwargs):
        rendered_titles.append((kwargs["start"], kwargs["end"]))
        _fake_render_writer(dst)
        return dst

    monkeypatch.setattr(progressive, "transcribe_single_chunk", fake_transcribe_single_chunk)
    monkeypatch.setattr(progressive, "analyze", fake_analyze)
    monkeypatch.setattr(progressive, "render", fake_render)

    report = progressive.run_progressive_pipeline(
        source,
        out_dir,
        top=2,
        chunk_duration_s=120.0,
        overlap_s=1.5,
        transcribe_concurrency=2,
        render_concurrency=1,
        checkpoint_path=checkpoint,
    )

    assert transcribed_indices == [1], "Chunk 0 from checkpoint must not be re-transcribed"
    assert report["status"] == "passed"
    assert report["transcription"]["chunksCompleted"] == 2
    assert len(report["clips"]) == 2
    # Prioritized order: highest score (chunk 0 resumed 0.91) then chunk 1 (0.85)
    assert rendered_titles[0] == (10.0, 30.0)
    saved = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert len(saved["completedChunks"]) == 2


def test_out_of_order_chunks_reconstruct_chronological_transcript_and_render_priority(tmp_path: Path, monkeypatch):
    source = _make_dummy_source(tmp_path / "long.mp4")
    out_dir = tmp_path / "out"

    monkeypatch.setattr(
        progressive,
        "ffprobe",
        lambda path, strict=True: {
            "duration": 360.0 if str(path) == str(source) else 25.0,
            "width": 1920 if str(path) == str(source) else 1080,
            "height": 1080 if str(path) == str(source) else 1920,
            "hasAudio": True,
            "format": "mp4",
        },
    )

    def fake_transcribe_single_chunk(win, **kwargs):
        idx = win["index"]
        # Force chunk 2 to complete before chunk 1 before chunk 0
        if idx == 0:
            time.sleep(0.12)
            segs = [{"start": 10.0, "end": 30.0, "text": "Early alpha"}]
        elif idx == 1:
            time.sleep(0.06)
            segs = [
                {"start": 119.2, "end": 121.0, "text": "Overlap bridge"},
                {"start": 130.0, "end": 155.0, "text": "Middle beta"},
            ]
        else:
            segs = [
                {"start": 239.0, "end": 241.0, "text": "Overlap late"},
                {"start": 260.0, "end": 285.0, "text": "Late gamma"},
            ]
        return {
            "index": idx,
            "start_time": win["start_time"],
            "end_time": win["end_time"],
            "language": "en",
            "segments": segs,
        }

    def fake_analyze(req):
        end_s = req.end_seconds or 360.0
        if end_s >= 280.0:
            return {"candidates": [{"start": 260.0, "end": 285.0, "score": 0.94, "title": "Late best"}]}
        if end_s >= 150.0:
            return {"candidates": [{"start": 130.0, "end": 155.0, "score": 0.70, "title": "Mid clip"}]}
        return {"candidates": [{"start": 10.0, "end": 30.0, "score": 0.96, "title": "Early best"}]}

    early_ready: list[str] = []

    def fake_render(src, dst, **kwargs):
        assert kwargs.get("single_pass") is True
        _fake_render_writer(dst)
        return dst

    monkeypatch.setattr(progressive, "transcribe_single_chunk", fake_transcribe_single_chunk)
    monkeypatch.setattr(progressive, "analyze", fake_analyze)
    monkeypatch.setattr(progressive, "render", fake_render)

    report = progressive.run_progressive_pipeline(
        source,
        out_dir,
        top=3,
        chunk_duration_s=120.0,
        overlap_s=1.5,
        transcribe_concurrency=3,
        render_concurrency=1,
        on_clip_ready=lambda clip: early_ready.append(clip["title"]),
    )

    assert report["status"] == "passed"
    assert len(early_ready) == 3
    transcript = json.loads((out_dir / "transcript.json").read_text(encoding="utf-8"))
    starts = [s["start"] for s in transcript["segments"]]
    assert starts == sorted(starts), "Transcript segments must be monotonically sorted regardless of chunk arrival order"
    assert report["milestones"]["firstAudioExtractAndTranscribeSeconds"] is not None
    assert report["milestones"]["firstPlayableClipSeconds"] is not None
    assert report["milestones"]["thirdPlayableClipSeconds"] is not None
    assert report["milestones"]["thirdPlayableClipSeconds"] >= report["milestones"]["firstPlayableClipSeconds"]


def test_partial_transcription_failure_continues_surviving_chunks(tmp_path: Path, monkeypatch):
    source = _make_dummy_source(tmp_path / "partial.mp4")
    out_dir = tmp_path / "out"

    monkeypatch.setattr(
        progressive,
        "ffprobe",
        lambda path, strict=True: {
            "duration": 240.0 if str(path) == str(source) else 20.0,
            "width": 1280 if str(path) == str(source) else 1080,
            "height": 720 if str(path) == str(source) else 1920,
            "hasAudio": True,
            "format": "mp4",
        },
    )

    def fake_transcribe_single_chunk(win, **kwargs):
        if win["index"] == 1:
            raise RuntimeError("Simulated Whisper worker fault on chunk 1")
        return {
            "index": win["index"],
            "start_time": win["start_time"],
            "end_time": win["end_time"],
            "language": "en",
            "segments": [{"start": 15.0, "end": 40.0, "text": "Surviving chunk zero speech"}],
        }

    monkeypatch.setattr(progressive, "transcribe_single_chunk", fake_transcribe_single_chunk)
    monkeypatch.setattr(
        progressive,
        "analyze",
        lambda req: {"candidates": [{"start": 15.0, "end": 40.0, "score": 0.87, "title": "Surviving clip"}]},
    )
    monkeypatch.setattr(
        progressive,
        "render",
        lambda src, dst, **kwargs: (_fake_render_writer(dst), dst)[1],
    )

    report = progressive.run_progressive_pipeline(
        source,
        out_dir,
        top=2,
        chunk_duration_s=120.0,
        transcribe_concurrency=2,
        render_concurrency=1,
    )

    assert report["status"] == "passed"
    assert report["transcription"]["chunksCompleted"] == 1
    assert report["transcription"]["chunksFailed"] == 1
    assert report["transcription"]["failedChunks"][0]["index"] == 1
    assert len(report["clips"]) == 1


def test_cancel_event_stops_progressive_pipeline(tmp_path: Path, monkeypatch):
    source = _make_dummy_source(tmp_path / "cancel.mp4")
    out_dir = tmp_path / "out"
    cancel_event = threading.Event()

    monkeypatch.setattr(
        progressive,
        "ffprobe",
        lambda path, strict=True: {
            "duration": 360.0 if str(path) == str(source) else 20.0,
            "width": 1920,
            "height": 1080,
            "hasAudio": True,
            "format": "mp4",
        },
    )

    def fake_transcribe_single_chunk(win, **kwargs):
        if win["index"] == 0:
            cancel_event.set()
        else:
            time.sleep(0.15)
        return {
            "index": win["index"],
            "start_time": win["start_time"],
            "end_time": win["end_time"],
            "language": "en",
            "segments": [{"start": win["start_time"] + 5.0, "end": win["start_time"] + 15.0, "text": "Text"}],
        }

    monkeypatch.setattr(progressive, "transcribe_single_chunk", fake_transcribe_single_chunk)
    monkeypatch.setattr(
        progressive,
        "analyze",
        lambda req: {"candidates": [{"start": 5.0, "end": 25.0, "score": 0.82, "title": "Cancelled clip"}]},
    )
    monkeypatch.setattr(progressive, "render", lambda src, dst, **kwargs: (_fake_render_writer(dst), dst)[1])

    report = progressive.run_progressive_pipeline(
        source,
        out_dir,
        top=3,
        chunk_duration_s=120.0,
        transcribe_concurrency=1,
        render_concurrency=1,
        cancel_event=cancel_event,
    )

    assert report["status"] == "cancelled"
    assert report["transcription"]["chunksCompleted"] <= 1


def test_verified_mp4_rejects_corrupt_or_empty_outputs(tmp_path: Path, monkeypatch):
    source = _make_dummy_source(tmp_path / "bad_render.mp4")
    out_dir = tmp_path / "out"

    def fake_ffprobe(path, strict=True):
        if str(path) == str(source):
            return {"duration": 90.0, "width": 1920, "height": 1080, "hasAudio": True, "format": "mp4"}
        # Rendered file probes with invalid 0 duration -> must be rejected
        return {"duration": 0.0, "width": 0, "height": 0, "hasAudio": False, "format": "mp4"}

    monkeypatch.setattr(progressive, "ffprobe", fake_ffprobe)
    monkeypatch.setattr(
        progressive,
        "transcribe_single_chunk",
        lambda win, **kwargs: {
            "index": 0,
            "start_time": 0.0,
            "end_time": 90.0,
            "language": "en",
            "segments": [{"start": 5.0, "end": 30.0, "text": "Speech"}],
        },
    )
    monkeypatch.setattr(
        progressive,
        "analyze",
        lambda req: {"candidates": [{"start": 5.0, "end": 30.0, "score": 0.90, "title": "Corrupt render"}]},
    )
    monkeypatch.setattr(progressive, "render", lambda src, dst, **kwargs: (_fake_render_writer(dst, size=2048), dst)[1])

    report = progressive.run_progressive_pipeline(source, out_dir, top=1, chunk_duration_s=120.0)

    assert report["status"] == "no_candidates"
    assert report["clips"] == []
    assert len(report["analysis"]["renderErrors"]) == 1


def test_range_download_failure_never_falls_back_to_full_download(tmp_path: Path, monkeypatch):
    full_download_called = False

    def fail_if_full_called(*args, **kwargs):
        nonlocal full_download_called
        full_download_called = True
        return str(tmp_path / "full.mp4")

    monkeypatch.setattr(download_service, "is_safe_public_ip", lambda host: True)
    monkeypatch.setattr(download_service, "download", fail_if_full_called)
    monkeypatch.setattr(
        download_service.subprocess,
        "run",
        lambda *args, **kwargs: type("Proc", (), {"returncode": 1, "stderr": "section failed", "stdout": ""})(),
    )

    with pytest.raises(RuntimeError, match="Selected source range download failed"):
        download_service.download_range("https://www.youtube.com/watch?v=dQw4w9WgXcQ", str(tmp_path), 10.0, 70.0)

    assert full_download_called is False


def test_chunk_window_timestamp_reconstruction_and_boundary_dedup():
    windows = plan_chunk_windows(duration_s=250.0, chunk_duration_s=120.0, overlap_s=2.0)
    assert len(windows) >= 2
    assert windows[0]["start_time"] == 0.0
    assert windows[1]["start_time"] < windows[0]["end_time"]

    raw_segments = [
        {"start": 117.5, "end": 119.5, "text": "before boundary", "words": [{"start": 117.5, "end": 119.5, "word": "before"}]},
        {"start": 119.0, "end": 120.5, "text": "hello world", "words": [{"start": 119.0, "end": 119.7, "word": "hello"}, {"start": 119.8, "end": 120.5, "word": "world"}]},
        {"start": 119.2, "end": 120.6, "text": "hello world", "words": [{"start": 119.2, "end": 119.8, "word": "hello"}, {"start": 119.9, "end": 120.6, "word": "world"}]},
        {"start": 121.0, "end": 125.0, "text": "after boundary", "words": [{"start": 121.0, "end": 125.0, "word": "after"}]},
    ]
    deduped = deduplicate_boundary_words(raw_segments, tolerance_s=1.2)
    texts = [s["text"] for s in deduped]
    assert texts.count("hello world") == 1
    assert [s["start"] for s in deduped] == sorted(s["start"] for s in deduped)


def test_chunk_retry_and_timestamp_reconstruction():
    attempts = {"count": 0}

    def flaky_transcribe(audio, language=None):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("Transient chunk error")
        return {
            "language": "en",
            "segments": [
                {
                    "start": 2.0,
                    "end": 5.5,
                    "text": "Recovered phrase",
                    "words": [
                        {"start": 2.0, "end": 3.5, "word": "Recovered"},
                        {"start": 3.6, "end": 5.5, "word": "phrase"},
                    ],
                }
            ],
        }

    res = transcribe_single_chunk(
        {"index": 2, "start_time": 120.0, "end_time": 180.0, "audio": [0.1, 0.2]},
        transcribe_fn=flaky_transcribe,
        max_retries=1,
    )
    assert attempts["count"] == 2
    assert res["segments"][0]["start"] == 122.0
    assert res["segments"][0]["end"] == 125.5
    assert res["segments"][0]["words"][0]["start"] == 122.0
    assert res["segments"][0]["words"][1]["end"] == 125.5
