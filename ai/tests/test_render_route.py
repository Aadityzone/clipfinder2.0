from unittest.mock import patch

from fastapi.testclient import TestClient

from ai import main


client = TestClient(main.app)


def request_body(tmp_path, **overrides):
    body = {
        "input_path": str(tmp_path / "source.mp4"),
        "output_path": str(tmp_path / "output.mp4"),
        "start": 0,
        "end": 3,
        "segments": [{"start": 0, "end": 3}],
    }
    body.update(overrides)
    return body


def test_render_route_rejects_source_without_video_metadata(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "ffprobe", lambda _path: {"duration": 3, "width": 0, "height": 720})

    response = client.post("/v1/render", json=request_body(tmp_path))

    assert response.status_code == 400
    assert "valid video stream" in response.json()["detail"]


def test_render_route_rejects_invalid_segments_before_rendering(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "ffprobe", lambda _path: {"duration": 10, "width": 1280, "height": 720})
    render_mock = patch("ai.main.render")
    with render_mock as render_call:
        response = client.post(
            "/v1/render",
            json=request_body(tmp_path, segments=[{"start": 4, "end": 2}]),
        )

    assert response.status_code == 400
    render_call.assert_not_called()


def test_render_route_rejects_missing_render_artifact(monkeypatch, tmp_path):
    source = {"duration": 10, "width": 1280, "height": 720}
    monkeypatch.setattr(main, "ffprobe", lambda _path: source)
    monkeypatch.setattr(main, "render", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main.os.path, "isfile", lambda _path: False)

    response = client.post("/v1/render", json=request_body(tmp_path))

    assert response.status_code == 500
    assert "output was not created" in response.json()["detail"]


def test_render_route_rejects_unreadable_output_metadata(monkeypatch, tmp_path):
    probes = iter([
        {"duration": 10, "width": 1280, "height": 720},
        {"duration": 3, "width": None, "height": 1920},
    ])
    monkeypatch.setattr(main, "ffprobe", lambda _path: next(probes))
    monkeypatch.setattr(main, "render", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main.os.path, "isfile", lambda _path: True)
    monkeypatch.setattr(main.os.path, "getsize", lambda _path: 4096)

    response = client.post("/v1/render", json=request_body(tmp_path))

    assert response.status_code == 500
    assert "not a readable video" in response.json()["detail"]


def test_render_route_turns_ffprobe_timeout_into_failed_request(monkeypatch, tmp_path):
    import subprocess

    def timeout(_path):
        raise subprocess.TimeoutExpired(cmd="ffprobe", timeout=30)

    monkeypatch.setattr(main, "ffprobe", timeout)

    response = client.post("/v1/render", json=request_body(tmp_path))

    assert response.status_code == 500
    assert "timed out" in response.json()["detail"].lower()


def test_thumbnail_route_bounds_ffmpeg_execution(monkeypatch, tmp_path):
    import subprocess

    from ai import main

    def timeout(*_args, **kwargs):
        assert kwargs["timeout"] == 300
        raise subprocess.TimeoutExpired(cmd="ffmpeg", timeout=300)

    with patch("subprocess.run", side_effect=timeout):
        response = client.post(
            "/v1/thumbnail",
            json={
                "input_path": str(tmp_path / "source.mp4"),
                "output_path": str(tmp_path / "thumbnail.jpg"),
                "time": 1.5,
            },
        )

    assert response.status_code == 500
    assert "timed out" in response.json()["detail"].lower()
