from ai.scripts import smoke_real_video


def test_smoke_pipeline_runs_ingest_transcribe_analyze_render_in_order(monkeypatch, tmp_path):
    calls = []

    def fake_post(base_url, path, payload, secret):
        calls.append((base_url, path, payload, secret))
        if path == "/v1/ingest":
            return {
                "media_path": "/shared/source.mp4",
                "metadata": {
                    "duration": 60,
                    "width": 1920,
                    "height": 1080,
                    "codec": "h264",
                    "hasAudio": True,
                },
            }
        if path == "/v1/transcribe":
            return {
                "language": "en",
                "text": "That was unexpected",
                "segments": [{"start": 12, "end": 24, "text": "That was unexpected"}],
            }
        if path == "/v1/analyze":
            return {"candidates": [
                {"start": 12, "end": 24, "score": 80, "category": "AI Detect", "rationale": "test"},
            ]}
        if path == "/v1/render":
            return {
                "output_path": payload["output_path"],
                "size": 8192,
                "duration": 12,
                "width": 1080,
                "height": 1920,
            }
        raise AssertionError(f"Unexpected endpoint: {path}")

    monkeypatch.setattr(smoke_real_video, "post_json", fake_post)

    report = smoke_real_video.run(
        "http://ai.test",
        "https://www.youtube.com/watch?v=authorized-fixture",
        str(tmp_path),
        "test-secret",
    )

    assert [call[1] for call in calls] == [
        "/v1/ingest", "/v1/transcribe", "/v1/analyze", "/v1/render",
    ]
    assert all(call[0] == "http://ai.test" for call in calls)
    assert all(call[3] == "test-secret" for call in calls)
    assert report["status"] == "passed"
    assert report["transcription"]["segment_count"] == 1
    assert report["analysis"]["candidate_count"] == 1
    assert report["render"]["size_bytes"] == 8192
    assert calls[-1][2]["segments"] == [{"start": 12.0, "end": 24.0}]


def test_smoke_pipeline_fails_when_analysis_has_no_candidates(monkeypatch, tmp_path):
    def fake_post(_base_url, path, payload, _secret):
        if path == "/v1/ingest":
            return {"media_path": "/shared/source.mp4", "metadata": {"duration": 30, "width": 1280, "height": 720}}
        if path == "/v1/transcribe":
            return {"language": "en", "text": "", "segments": []}
        if path == "/v1/analyze":
            return {"candidates": []}
        raise AssertionError(f"Render must not run after empty analysis: {path}")

    monkeypatch.setattr(smoke_real_video, "post_json", fake_post)

    try:
        smoke_real_video.run("http://ai.test", "https://youtu.be/fixture", str(tmp_path), None)
    except RuntimeError as exc:
        assert "no candidates" in str(exc)
    else:
        raise AssertionError("Expected empty candidate analysis to fail the smoke test")


def test_smoke_pipeline_rejects_candidate_clamped_to_zero_duration(monkeypatch, tmp_path):
    def fake_post(_base_url, path, _payload, _secret):
        if path == "/v1/ingest":
            return {"media_path": "/shared/source.mp4", "metadata": {"duration": 30, "width": 1280, "height": 720}}
        if path == "/v1/transcribe":
            return {"language": "en", "text": "", "segments": []}
        if path == "/v1/analyze":
            return {"candidates": [
                {"start": 30, "end": 30.02, "score": 100, "category": "AI Detect"},
            ]}
        raise AssertionError(f"Render must not run for a zero-duration segment: {path}")

    monkeypatch.setattr(smoke_real_video, "post_json", fake_post)

    try:
        smoke_real_video.run("http://ai.test", "https://youtu.be/fixture", str(tmp_path), None)
    except RuntimeError as exc:
        assert "valid source timestamps" in str(exc)
    else:
        raise AssertionError("Expected the invalid candidate to be rejected")
