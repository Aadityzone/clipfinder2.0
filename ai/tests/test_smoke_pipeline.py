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
