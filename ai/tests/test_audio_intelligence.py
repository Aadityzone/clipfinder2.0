from subprocess import TimeoutExpired

from ai.services import audio_intelligence as audio


def test_missing_audio_file_returns_no_windows(monkeypatch):
    monkeypatch.setattr(audio.os.path, "isfile", lambda _path: False)

    assert audio.loudness_windows("missing.mp4") == []


def test_probe_timeout_returns_no_windows(monkeypatch):
    monkeypatch.setattr(audio.os.path, "isfile", lambda _path: True)

    def timeout(*_args, **_kwargs):
        raise TimeoutExpired("ffprobe", 20)

    monkeypatch.setattr(audio.subprocess, "run", timeout)

    assert audio.loudness_windows("slow.mp4") == []


def test_failed_audio_sample_keeps_bounded_timeline_without_fake_energy(monkeypatch):
    monkeypatch.setattr(audio.os.path, "isfile", lambda _path: True)

    class Probe:
        stdout = "11"

    calls = {"count": 0}

    def run(args, **kwargs):
        calls["count"] += 1
        assert "timeout" in kwargs
        if args[0] == "ffprobe":
            return Probe()
        if calls["count"] == 2:
            raise TimeoutExpired("ffmpeg", 30)

        class Sample:
            stderr = "mean_volume: -22.5 dB\nmax_volume: -2.0 dB\n"
            returncode = 0

        return Sample()

    monkeypatch.setattr(audio.subprocess, "run", run)

    result = audio.loudness_windows("sample.mp4", window=5)

    assert len(result) == 3
    assert result[0]["start"] == 0
    assert result[0]["end"] == 5
    assert result[0]["meanDb"] == -22.5
    assert result[1]["meanDb"] is None
    assert result[1]["peakDb"] is None
    assert result[1]["energy"] == 0.0
    assert result[-1]["end"] == 11


def test_summarize_window_uses_loudest_peak_not_least_negative():
    result = audio.summarize_window(
        [
            {"start": 0, "end": 5, "meanDb": -20, "peakDb": -8},
            {"start": 5, "end": 10, "meanDb": -24, "peakDb": -2},
        ],
        0,
        10,
    )

    assert result["meanDb"] == -22
    assert result["peakDb"] == -2
