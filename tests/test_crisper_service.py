from types import SimpleNamespace

import pytest

from singlayer.crisper_service import SERVICE, infer
from singlayer.live_transcription import wav_window


def test_crisper_api_receives_audio_detected_language_and_word_flag():
    class Engine:
        def __init__(self):
            self.model = self
        def extract_features(self, audio):
            assert audio.shape == (16000,)
            return "features"
        def detect_language(self, features):
            assert features == "features"
            return [[("<|ja|>", .96)]]

    class Model:
        _engine = Engine()
        def transcribe(self, audio, **options):
            assert options == {"sr": 16000, "language": "ja", "word_timestamps": True, "mode": "verbatim"}
            assert float(audio[0]) == pytest.approx(.5)
            return SimpleNamespace(language="ja", words=[SimpleNamespace(word="夜", start=.1, end=.6)])

    output = infer(Model(), wav_window(b"\x00\x40" * 16000))
    assert output == {"service": SERVICE, "language": "ja", "words": [{"word": "夜", "start": .1, "end": .6}]}


def test_invalid_audio_never_reaches_model():
    import wave

    with pytest.raises((wave.Error, EOFError, ValueError)):
        infer(None, b"not a wave")
