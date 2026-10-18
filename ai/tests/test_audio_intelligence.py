import io
import subprocess
from types import SimpleNamespace

import numpy as np

from ai.services import audio_intelligence as audio


def test_window_stats_distinguishes_silence_from_audio():
    silence = np.zeros(800, dtype=np.float32)
    tone = np.full(800, 0.5, dtype=np.float32)

    silent_mean, silent_peak, silent_energy = audio._window_stats(silence)
    tone_mean, tone_peak, tone_energy = audio._window_stats(tone)

    assert silent_mean == -120.0
    assert silent_peak == -120.0
    assert silent_energy == 0.0
    assert tone_mean > silent_mean
    assert tone_peak > silent_peak
    assert tone_energy > 0.0


def test_loudness_windows_streams_pcm_through_one_ffmpeg_process(monkeypatch, tmp_path):
    media = tmp_path / "source.mp4"
    media.write_bytes(b"media")
    monkeypatch.setattr(audio.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(
        returncode=0, stdout="10.0"
    ))
    pcm = np.concatenate([
        np.full(8000 * 5, 0.1, dtype="<f4"),
        np.full(8000 * 5, 0.8, dtype="<f4"),
    ]).tobytes()
    launches = []

    class FakeProcess:
        def __init__(self):
            self.stdout = io.BytesIO(pcm)
            self.returncode = None

        def wait(self):
            self.returncode = 0
            return 0

        def poll(self):
            return self.returncode

        def kill(self):
            self.returncode = -9

    def fake_popen(command, **kwargs):
        launches.append(command)
        return FakeProcess()

    monkeypatch.setattr(audio.subprocess, "Popen", fake_popen)
    result = audio.loudness_windows(str(media))

    assert len(launches) == 1
    assert len(result) == 2
    assert result[0]["start"] == 0.0
    assert result[0]["end"] == 5.0
    assert result[1]["start"] == 5.0
    assert result[1]["end"] == 10.0
    assert result[1]["energy"] > result[0]["energy"]


def test_loudness_windows_returns_empty_for_missing_media(tmp_path):
    assert audio.loudness_windows(str(tmp_path / "missing.mp4")) == []


def test_loudness_windows_handles_process_timeout(monkeypatch, tmp_path):
    media = tmp_path / "source.mp4"
    media.write_bytes(b"media")
    monkeypatch.setattr(audio.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(
        returncode=0, stdout="10.0"
    ))
    pcm = np.full(8000 * 5, 0.5, dtype="<f4").tobytes()

    class HangingProcess:
        def __init__(self):
            self.stdout = io.BytesIO(pcm)
            self.returncode = None
            self.killed = False

        def wait(self, timeout=None):
            if not self.killed:
                raise subprocess.TimeoutExpired("ffmpeg", 5)
            self.returncode = -9
            return -9

        def poll(self):
            return self.returncode

        def kill(self):
            self.killed = True
            self.returncode = -9

    monkeypatch.setattr(audio.subprocess, "Popen", lambda *args, **kwargs: HangingProcess())
    result = audio.loudness_windows(str(media))
    assert len(result) >= 1

