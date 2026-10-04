import pytest

from singlayer.transcription import transcript_document


def test_segment_times_anchor_to_capture_not_response():
    payload = {"words": [{"start": 1, "end": 3, "word": "Original demo", "no_speech_prob": 0.1}]}
    result = transcript_document(payload, 50, 12)
    assert result["lines"][0]["start"] == 51
    assert result["lines"][0]["end"] == 53
    assert result["timing"] == "Word"
    assert "estimada" in result["sourceName"]


def test_no_timed_words_is_not_invented_lyrics():
    assert transcript_document({"words": []}, 0, 12) is None


@pytest.mark.parametrize("start,end", [(-1, 2), (3, 1), (1, 20), (float("nan"), 2)])
def test_bad_timestamps_rejected(start, end):
    with pytest.raises(ValueError):
        transcript_document({"words": [{"start": start, "end": end, "word": "Demo"}]}, 0, 12)


def test_word_timestamps_survive_browser_anchor_and_overlay_protocol():
    from kotonoha.lyrics.protocol import AdapterProtocolDecoder

    from singlayer.overlay_link import snapshot

    payload = {"words": [
        {"word": "Hello", "start": 1, "end": 1.4},
        {"word": "world.", "start": 1.5, "end": 2.1},
        {"word": "Next", "start": 3, "end": 3.4},
    ]}
    doc = transcript_document(payload, 50, 12)
    assert doc["lines"][0]["text"] == "Hello world."
    assert doc["lines"][0]["words"][1]["start"] == 51.5
    assert doc["lines"][0]["words"][1]["end"] == 52.1
    assert doc["lines"][1]["start"] == 53
    track = {"id": "demo", "title": "Test", "position": 51, "playing": True, "duration": 100}
    AdapterProtocolDecoder().decode(snapshot(track, doc, 1), observed_at=0)


def test_cjk_characters_keep_original_joining():
    doc = transcript_document({"language": "ja", "words": [
        {"word": "静", "start": 0, "end": .2}, {"word": "か", "start": .2, "end": .4},
    ]}, 0, 12)
    assert doc["lines"][0]["text"] == "静か"


@pytest.mark.parametrize("words", [None, [{"word": "x", "start": 1, "end": 2},
                                         {"word": "y", "start": 1.5, "end": 3}]])
def test_invalid_word_contract_rejected(words):
    with pytest.raises(ValueError):
        transcript_document({"words": words}, 0, 12)
