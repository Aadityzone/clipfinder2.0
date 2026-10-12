from types import SimpleNamespace

from ai import transcribe as transcription


class FakeWhisperModel:
    def transcribe(self, path, **options):
        assert path == "fixture.mp4"
        assert options == {
            "language": None,
            "word_timestamps": True,
            "vad_filter": True,
        }
        segments = [
            SimpleNamespace(
                start=-2,
                end=8,
                text="  bounded speech  ",
                words=[
                    SimpleNamespace(start=-1, end=1, word=" bounded", probability=.9),
                    SimpleNamespace(start=4, end=8, word=" speech", probability=float("nan")),
                    SimpleNamespace(start=7, end=6, word="invalid", probability=.5),
                ],
            ),
            SimpleNamespace(start=9, end=11, text="past end", words=[]),
            SimpleNamespace(start=float("nan"), end=4, text="bad", words=[]),
        ]
        return iter(segments), SimpleNamespace(duration=5, language="en")


def test_transcription_returns_only_finite_in_media_segment_and_word_times(monkeypatch):
    monkeypatch.setattr(transcription, "_model", FakeWhisperModel())

    result = transcription.transcribe("fixture.mp4")

    assert result["duration"] == 5
    assert result["language"] == "en"
    assert result["text"] == "bounded speech"
    assert len(result["segments"]) == 1
    segment = result["segments"][0]
    assert (segment["start"], segment["end"]) == (0, 5)
    assert [(word["start"], word["end"]) for word in segment["words"]] == [
        (0, 1), (4, 5)
    ]
    assert segment["words"][1]["confidence"] is None


def test_transcription_derives_duration_when_whisper_does_not_report_it(monkeypatch):
    class MissingDurationModel:
        def transcribe(self, _path, **_options):
            segments = [
                SimpleNamespace(start=1, end=3, text="speech", words=[]),
                SimpleNamespace(start=float("nan"), end=50, text="invalid", words=[]),
            ]
            return iter(segments), SimpleNamespace(duration=None, language="en")

    monkeypatch.setattr(transcription, "_model", MissingDurationModel())

    result = transcription.transcribe("fixture.mp4")

    assert result["duration"] == 3
    assert result["segments"] == [{
        "start": 1,
        "end": 3,
        "text": "speech",
        "confidence": None,
        "words": [],
    }]
