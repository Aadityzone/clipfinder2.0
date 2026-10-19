from ai.scripts.smoke_pipeline import _captions_for_clip, _number


def test_smoke_caption_cues_are_clipped_and_made_relative_to_clip():
    segments = [
        {"start": 2, "end": 5, "text": "starts before clip"},
        {"start": 4, "end": 7, "text": "crosses clip"},
        {"start": 9, "end": 11, "text": "outside clip"},
        {"start": 8, "end": 8, "text": "invalid interval"},
        {"start": 4, "end": 6, "text": ""},
    ]

    assert _captions_for_clip(segments, 4, 8) == [
        {"start": 0.0, "end": 1.0, "text": "starts before clip"},
        {"start": 0.0, "end": 3.0, "text": "crosses clip"},
    ]


def test_smoke_number_rejects_nan_and_invalid_values():
    assert _number("12.5") == 12.5
    assert _number("nan", 7) == 7
    assert _number("invalid", 3) == 3



def test_smoke_report_source_label_preserves_public_url_for_downloaded_temp_source(monkeypatch, tmp_path):
    import json
    from ai.scripts import smoke_pipeline

    source = tmp_path / "downloaded-temp.mp4"
    source.write_bytes(b"video")
    output = tmp_path / "output"
    monkeypatch.setattr(smoke_pipeline, "ffprobe", lambda _path: {
        "duration": 10, "width": 640, "height": 360, "hasAudio": True,
    })
    monkeypatch.setattr(smoke_pipeline, "transcribe", lambda *_args: {
        "language": "en", "text": "hello world",
        "segments": [{"start": 1, "end": 3, "text": "hello world"}],
    })
    monkeypatch.setattr(smoke_pipeline, "analyze", lambda *_args: {"candidates": [
        {"start": 1, "end": 3, "score": 80, "title": "Hello", "category": "AI Detect"}
    ]})
    def fake_render(_source, output_path, **_kwargs):
        from pathlib import Path
        Path(output_path).write_bytes(b"x" * 2048)
    monkeypatch.setattr(smoke_pipeline, "render", fake_render)

    report = smoke_pipeline.run_pipeline(
        source, output, source_label="https://example.com/public-video", top=1
    )

    assert report["source"] == "https://example.com/public-video"
    assert json.loads((output / "report.json").read_text())["source"] == "https://example.com/public-video"


def test_smoke_failure_writes_machine_readable_report(monkeypatch, tmp_path, capsys):
    import json
    from ai.scripts import smoke_pipeline

    output = tmp_path / "failed-run"
    def fail_download(_url, _temporary):
        raise RuntimeError("source provider rejected request")
    monkeypatch.setattr(smoke_pipeline, "download", fail_download)
    monkeypatch.setattr(
        "sys.argv",
        ["smoke_pipeline.py", "--url", "https://example.com/video", "--out-dir", str(output)],
    )

    assert smoke_pipeline.main() == 1
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert report["stage"] == "download"
    assert report["source"] == "https://example.com/video"
    assert report["errorType"] == "RuntimeError"
    assert "provider rejected request" in report["error"]
    assert json.loads(capsys.readouterr().err)["status"] == "failed"


def test_smoke_report_identifies_analysis_failure_for_url_source(monkeypatch, tmp_path, capsys):
    import json
    from ai.scripts import smoke_pipeline

    source = tmp_path / "source.mp4"
    source.write_bytes(b"input")
    output = tmp_path / "failed-analysis"
    monkeypatch.setattr(smoke_pipeline, "download", lambda *_args: str(source))
    monkeypatch.setattr(smoke_pipeline, "ffprobe", lambda _path: {
        "duration": 20, "width": 640, "height": 360, "hasAudio": True,
    })
    monkeypatch.setattr(smoke_pipeline, "transcribe", lambda *_args: {
        "language": "en", "text": "hello", "segments": [],
    })
    def fail_analysis(*_args):
        raise ValueError("analysis contract failed")
    monkeypatch.setattr(smoke_pipeline, "analyze", fail_analysis)
    monkeypatch.setattr(
        "sys.argv",
        ["smoke_pipeline.py", "--url", "https://example.com/video", "--out-dir", str(output)],
    )

    assert smoke_pipeline.main() == 1
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert report["stage"] == "analysis"
    assert report["errorType"] == "ValueError"
    assert report["source"] == "https://example.com/video"
    assert "analysis contract failed" in capsys.readouterr().err


def test_smoke_rejects_render_that_is_not_probeable_video(monkeypatch, tmp_path):
    import pytest
    from ai.scripts import smoke_pipeline

    source = tmp_path / "source.mp4"
    source.write_bytes(b"input")
    probes = iter([
        {"duration": 20, "width": 640, "height": 360},
        {"duration": 0, "width": None, "height": None},
    ])
    monkeypatch.setattr(smoke_pipeline, "ffprobe", lambda _path: next(probes))
    monkeypatch.setattr(smoke_pipeline, "transcribe", lambda *_args: {
        "language": "en", "text": "hello", "segments": [],
    })
    monkeypatch.setattr(smoke_pipeline, "analyze", lambda *_args: {"candidates": [
        {"start": 1, "end": 3, "score": 80},
    ]})
    def fake_render(_source, output_path, **_kwargs):
        from pathlib import Path
        Path(output_path).write_bytes(b"not actually an mp4")
    monkeypatch.setattr(smoke_pipeline, "render", fake_render)

    with pytest.raises(smoke_pipeline.SmokeStageError, match="not a playable video") as failure:
        smoke_pipeline.run_pipeline(source, tmp_path / "out")

    assert failure.value.stage == "render"



def test_smoke_invalid_source_metadata_is_reported_as_media_probe_failure(monkeypatch, tmp_path):
    import pytest
    from ai.scripts import smoke_pipeline

    source = tmp_path / "source.mp4"
    source.write_bytes(b"input")
    monkeypatch.setattr(smoke_pipeline, "ffprobe", lambda _path: {
        "duration": 0, "width": None, "height": None, "hasAudio": False,
    })

    with pytest.raises(smoke_pipeline.SmokeStageError, match="no valid duration") as failure:
        smoke_pipeline.run_pipeline(source, tmp_path / "out")

    assert failure.value.stage == "media_probe"
    assert failure.value.error_type == "RuntimeError"


def test_smoke_report_includes_label_free_selection_diagnostics(monkeypatch, tmp_path):
    """The smoke report must expose selection shape without claiming quality."""
    from ai.scripts import smoke_pipeline

    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    output = tmp_path / "out"
    monkeypatch.setattr(
        smoke_pipeline,
        "ffprobe",
        lambda candidate: {"duration": 3600.0, "width": 1280, "height": 720, "hasAudio": True}
        if str(candidate).endswith("source.mp4")
        else {"duration": 12.0, "width": 1080, "height": 1920, "hasAudio": True},
    )
    monkeypatch.setattr(smoke_pipeline, "transcribe", lambda *_args: {
        "language": "en", "text": "hello",
        "segments": [{"start": 1, "end": 3, "text": "hello"}],
    })
    # Two candidates clustered in the first two minutes of a one-hour source.
    monkeypatch.setattr(smoke_pipeline, "analyze", lambda *_args: {"candidates": [
        {"start": 10.0, "end": 25.0, "score": 95, "title": "A", "category": "AI Detect"},
        {"start": 40.0, "end": 55.0, "score": 94, "title": "B", "category": "AI Detect"},
        {"start": 200.0, "end": 215.0, "score": 93, "title": "C", "category": "AI Detect"},
    ]})
    def fake_render(_source, output_path, **_kwargs):
        from pathlib import Path
        Path(output_path).write_bytes(b"x" * 2048)
    monkeypatch.setattr(smoke_pipeline, "render", fake_render)

    report = smoke_pipeline.run_pipeline(source, output, top=2)
    selection = report["analysis"]["selection"]

    assert report["status"] == "passed"
    assert report["analysis"]["renderedCount"] == 2
    assert selection["candidateCount"] == 3
    assert selection["duplicateRate"] == 0.0
    assert selection["totalWindowCount"] == 30
    assert selection["densestWindowShare"] == round(2 / 3, 4)
    assert any("not a quality score" in note for note in report["limitations"])

