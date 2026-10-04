import pytest

from singlayer.transcription import whisper_document


def payload(words=None, **overrides):
    segment = {"text": " Good morning", "start": 1, "end": 3, "no_speech_prob": .1,
               "words": words or [{"word": " Good", "start": 1, "end": 1.5},
                                   {"word": " mor", "start": 1.5, "end": 2},
                                   {"word": "ning", "start": 2, "end": 3}]}
    return {"segments": [{**segment, **overrides}]}


def test_subword_tokens_join_without_inventing_spaces_or_times():
    doc = whisper_document(payload(), 40, 12)
    line = doc["lines"][0]
    assert (line["start"], line["end"]) == (41, 43)
    assert [w["text"] for w in line["words"]] == [" Good", " morning"]
    assert (line["words"][1]["start"], line["words"][1]["end"]) == (41.5, 43)


def test_invalid_token_timing_keeps_only_measured_segment():
    doc = whisper_document(payload([{ "word": " Good morning", "start": -1, "end": 30}]), 0, 12)
    assert doc["timing"] == "Line"
    assert doc["lines"][0]["words"] == []
    assert doc["lines"][0]["end"] == 3


def test_silence_and_invalid_segments_never_become_lyrics():
    assert whisper_document(payload(no_speech_prob=.9), 0, 12) is None
    for change in ({"end": 40}, {"start": float("nan")}, {"text": "bad\x00text"}):
        with pytest.raises(ValueError):
            whisper_document(payload(**change), 0, 12)


def test_dtw_envelope_excludes_leading_music_without_claiming_word_boundaries():
    data = payload()
    data["segments"][0]["start"] = 0
    for token, center in zip(data["segments"][0]["words"], [125, 220, 280]):
        token["t_dtw"] = center
    doc = whisper_document(data, 40, 12)
    assert doc["timing"] == "Line"
    assert doc["lines"][0]["start"] == 41.25
    assert doc["lines"][0]["end"] == 42.8
    assert doc["lines"][0]["words"] == []
