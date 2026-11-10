import subprocess

import pytest

from ai.services.video_context import build_visual_context, extract_sampled_frames, video_stream_info
from ai.services.visual_candidates import multimodal_event_candidates


def _ffmpeg_video(path, duration=6, rate=24):
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", f"testsrc2=size=320x240:rate={rate}:duration={duration}",
        "-c:v", "mpeg4", "-q:v", "5", str(path),
    ], check=True, timeout=30)


def test_extracts_sparse_source_presentation_timestamps_and_cleans_temp_frames(tmp_path):
    video = tmp_path / "sample.mp4"
    _ffmpeg_video(video)

    result = extract_sampled_frames(str(video), interval_s=1, max_frames=4)

    assert result["available"] is True
    assert result["sampling"] == "ffmpeg_fps_filter"
    assert len(result["frames"]) == 4
    timestamps = [row["timestampS"] for row in result["frames"]]
    assert timestamps == sorted(set(timestamps))
    assert timestamps[0] == pytest.approx(0, abs=0.02)
    assert timestamps[1] == pytest.approx(1, abs=0.02)
    assert all(row["frameRef"]["timestampS"] == row["timestampS"] for row in result["frames"])
    assert len(result["visualSamples"]) == len(result["frames"])
    assert all("visualChange" in row and "motion" in row for row in result["visualSamples"])
    assert not list(tmp_path.glob("clipfinder-frames-*"))


def test_caps_long_video_frame_count(tmp_path):
    video = tmp_path / "long.mp4"
    _ffmpeg_video(video, duration=20)

    result = extract_sampled_frames(str(video), interval_s=0.25, max_frames=5)

    assert result["available"] is True
    assert result["frameCount"] == 5
    assert result["frames"][-1]["timestampS"] < 2


def test_vfr_timestamps_follow_presentation_pts_not_nominal_rate(tmp_path):
    video = tmp_path / "variable-rate.mp4"
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=10:duration=2",
        "-vf", r"setpts=if(lt(N\,10)\,N/(10*TB)\,(N+10)/(10*TB))",
        "-fps_mode", "vfr", "-c:v", "mpeg4", "-q:v", "5", str(video),
    ], check=True, timeout=30)

    result = extract_sampled_frames(str(video), interval_s=0.5, max_frames=20)

    timestamps = [row["timestampS"] for row in result["frames"]]
    assert result["available"] is True
    assert len(timestamps) >= 5
    assert result["durationS"] > 2.5
    assert timestamps[-1] == pytest.approx(2.5, abs=0.1)


def test_handles_missing_video_stream(tmp_path):
    audio = tmp_path / "audio-only.mp4"
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-vn", str(audio),
    ], check=True, timeout=30)

    assert video_stream_info(str(audio)) == {"available": False, "reason": "no video stream"}
    result = extract_sampled_frames(str(audio))
    assert result["available"] is False
    assert result["frames"] == []


def test_scene_context_aligns_transcript_audio_ocr_and_frame_references():
    result = build_visual_context(
        {"available": True, "durationS": 12, "frames": [
            {"timestampS": 2.0, "frameRef": {"type": "source_timestamp", "timestampS": 2.0}},
            {"timestampS": 9.0, "frameRef": {"type": "source_timestamp", "timestampS": 9.0}},
        ]},
        scenes={"sceneChanges": [6]},
        visual_samples={"samples": [{"time": 2, "motion": 0.4, "visualChange": 0.9}]},
        on_screen={"samples": [{"time": 2, "ocrText": "SCORE 100"}]},
        audio_windows=[{"start": 1, "end": 3, "energy": 0.8}],
        transcript_segments=[{"start": 1.2, "end": 2.4, "text": "What a move", "speakerId": "speaker_1"}],
    )

    assert len(result["scenes"]) == 2
    assert result["scenes"][0]["endS"] == 6
    assert result["scenes"][0]["frameReferences"][0]["timestampS"] == 2
    assert result["scenes"][0]["transcriptContext"][0]["text"] == "What a move"
    assert result["scenes"][0]["audioEvidence"]["windowCount"] == 1
    assert result["scenes"][0]["onScreenText"] == ["SCORE 100"]
    assert result["scenes"][0]["semanticDescription"] is None


def test_ffprobe_failure_is_reported_without_fabricated_metadata(monkeypatch):
    def fail(*_args, **_kwargs):
        raise subprocess.CalledProcessError(1, "ffprobe")

    monkeypatch.setattr(subprocess, "run", fail)
    result = video_stream_info("broken.mp4")
    assert result["available"] is False
    assert result["reason"] == "ffprobe failed (CalledProcessError)"
    assert "durationS" not in result


def test_visual_candidate_carries_relevant_source_frame_reference():
    result = multimodal_event_candidates(
        [],
        {
            "visual": {"samples": [{"time": 10, "visualChange": 0.95, "motion": 0.5}]},
            "frameAnalysis": {"frames": [
                {"timestampS": 8, "frameRef": {"type": "source_timestamp", "timestampS": 8}},
                {"timestampS": 40, "frameRef": {"type": "source_timestamp", "timestampS": 40}},
            ]},
        },
        duration=60,
    )

    assert result[0]["features"]["frameReferences"] == [
        {"type": "source_timestamp", "timestampS": 8}
    ]
