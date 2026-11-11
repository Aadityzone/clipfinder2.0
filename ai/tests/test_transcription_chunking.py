from unittest.mock import MagicMock
import numpy as np
import pytest

from ai.services.transcription_chunking import (
    deduplicate_boundary_words,
    split_audio_chunks,
    transcribe_chunked,
    transcribe_single_chunk,
)


def test_split_audio_chunks_divides_correctly_with_overlap():
    sample_rate = 16000
    # 400 seconds of audio
    total_samples = 400 * sample_rate
    audio = np.zeros(total_samples, dtype=np.float32)

    chunk_duration_s = 100.0
    overlap_s = 2.0

    chunks = split_audio_chunks(
        audio,
        sample_rate=sample_rate,
        chunk_duration_s=chunk_duration_s,
        overlap_s=overlap_s,
    )

    # 400 seconds with 100s chunks -> 4 chunks:
    # 0: [0, 102], 1: [100, 202], 2: [200, 302], 3: [300, 400]
    assert len(chunks) == 4
    assert chunks[0]["start_time"] == 0.0
    assert chunks[0]["end_time"] == 102.0
    assert chunks[0]["is_last"] is False

    assert chunks[1]["start_time"] == 100.0
    assert chunks[1]["end_time"] == 202.0

    assert chunks[2]["start_time"] == 200.0
    assert chunks[2]["end_time"] == 302.0

    assert chunks[3]["start_time"] == 300.0
    assert chunks[3]["end_time"] == 400.0
    assert chunks[3]["is_last"] is True


def test_deduplicate_boundary_words_suppresses_overlap_duplicates():
    # Chunk 1 ends with "amazing sunset" at t=99.5 - 100.8
    # Chunk 2 begins with "sunset over the mountains" at t=100.5 - 103.0
    segments = [
        {
            "start": 98.0,
            "end": 100.8,
            "text": "What an amazing sunset",
            "words": [
                {"start": 98.0, "end": 98.4, "word": "What"},
                {"start": 98.5, "end": 98.7, "word": "an"},
                {"start": 98.8, "end": 99.4, "word": "amazing"},
                {"start": 99.5, "end": 100.7, "word": "sunset"},
            ],
        },
        {
            "start": 100.4,
            "end": 103.2,
            "text": "sunset over the mountains",
            "words": [
                # Duplicate "sunset" within 0.75s tolerance of previous sunset (at 99.5)
                {"start": 100.4, "end": 100.9, "word": "sunset"},
                {"start": 101.0, "end": 101.4, "word": "over"},
                {"start": 101.5, "end": 101.7, "word": "the"},
                {"start": 101.8, "end": 102.8, "word": "mountains"},
            ],
        },
    ]

    cleaned = deduplicate_boundary_words(segments, tolerance_s=1.0)
    assert len(cleaned) == 2
    # The duplicate "sunset" in chunk 2 must be removed
    chunk2_words = [w["word"] for w in cleaned[1]["words"]]
    assert "sunset" not in chunk2_words
    assert chunk2_words == ["over", "the", "mountains"]
    assert cleaned[1]["text"] == "over the mountains"


def test_transcribe_single_chunk_shifts_timestamps():
    chunk = {
        "index": 1,
        "start_time": 120.0,
        "end_time": 242.0,
        "duration": 122.0,
        "audio": np.zeros(16000 * 10, dtype=np.float32),
    }

    mock_result = {
        "language": "en",
        "segments": [
            {
                "start": 1.0,
                "end": 4.5,
                "text": "Hello world",
                "words": [
                    {"start": 1.0, "end": 2.0, "word": "Hello"},
                    {"start": 2.1, "end": 4.5, "word": "world"},
                ],
            }
        ],
    }

    result = transcribe_single_chunk(chunk, language="en", transcribe_fn=lambda *a, **kw: mock_result)
    assert result["index"] == 1
    assert result["start_time"] == 120.0
    seg = result["segments"][0]
    assert seg["start"] == 121.0
    assert seg["end"] == 124.5
    assert seg["words"][0]["start"] == 121.0
    assert seg["words"][0]["end"] == 122.0
    assert seg["words"][1]["start"] == 122.1
    assert seg["words"][1]["end"] == 124.5


def test_transcribe_single_chunk_retries_on_failure():
    chunk = {
        "index": 0,
        "start_time": 0.0,
        "end_time": 60.0,
        "duration": 60.0,
        "audio": np.zeros(16000 * 5, dtype=np.float32),
    }

    attempts = 0

    def flaky_transcribe(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise RuntimeError("Transient device timeout")
        return {"language": "en", "segments": [{"start": 0.0, "end": 1.0, "text": "Recovered", "words": []}]}

    result = transcribe_single_chunk(chunk, transcribe_fn=flaky_transcribe, max_retries=2)
    assert attempts == 2
    assert result["segments"][0]["text"] == "Recovered"


def test_transcribe_chunked_bypasses_short_audio():
    # 30 seconds of audio should bypass chunking
    short_audio = np.zeros(30 * 16000, dtype=np.float32)
    mock_fn = MagicMock(return_value={
        "language": "en",
        "text": "Short clip",
        "segments": [{"start": 0.0, "end": 2.0, "text": "Short clip", "words": []}],
        "duration": 30.0,
    })

    result = transcribe_chunked(
        short_audio,
        chunk_duration_s=180.0,
        overlap_s=1.0,
        transcribe_fn=mock_fn,
    )

    mock_fn.assert_called_once()
    assert result["text"] == "Short clip"


def test_transcribe_chunked_processes_parallel_and_reconstructs_text():
    # 400 seconds of audio, chunked into 100s pieces
    audio = np.zeros(400 * 16000, dtype=np.float32)

    def fake_transcribe(chunk_slice, language=None):
        return {
            "language": "en",
            "segments": [
                {
                    "start": 5.0,
                    "end": 15.0,
                    "text": "Piece",
                    "words": [{"start": 5.0, "end": 15.0, "word": "Piece"}],
                }
            ],
        }

    progress_reports = []

    result = transcribe_chunked(
        audio,
        chunk_duration_s=100.0,
        overlap_s=2.0,
        concurrency=2,
        transcribe_fn=fake_transcribe,
        progress_callback=lambda done, total: progress_reports.append((done, total)),
    )

    assert len(result["segments"]) == 4
    # All 4 chunks reported progress
    assert len(progress_reports) == 4
    assert progress_reports[-1] == (4, 4)
    # Timestamps properly shifted: chunk 0 is at +0, chunk 1 is at +100, chunk 2 is at +200, chunk 3 is at +300
    starts = [s["start"] for s in result["segments"]]
    assert starts == [5.0, 105.0, 205.0, 305.0]
    assert result["text"] == "Piece Piece Piece Piece"
