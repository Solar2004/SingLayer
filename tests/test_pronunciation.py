import json

import pytest

from singlayer.pronunciation import apply_guide, parse_guide


def test_parse_rejects_missing_reordered_or_extra_lines():
    good = {"lines": [{"id": 0, "phonetic": "Jelóu", "tip": "H aspirada"}]}
    assert parse_guide(json.dumps(good) + "<|stats|>{}<|/stats|>", ["Hello"])[0]["phonetic"] == "Jelóu"
    for bad in (
        {"lines": []},
        {"lines": [{"id": 1, "phonetic": "No"}]},
        {"lines": [{"id": 0, "phonetic": "\n"}]},
    ):
        with pytest.raises(ValueError):
            parse_guide(json.dumps(bad), ["Hello"])


def test_guide_preserves_timestamps_original_and_real_protocol():
    pytest.importorskip("kotonoha")
    from kotonoha.lyrics.lrc_parser import parse_lrc
    from kotonoha.lyrics.protocol import AdapterProtocolDecoder

    from singlayer.overlay_link import snapshot
    from singlayer.worker import document

    original = document(
        parse_lrc("[00:01.00]<00:01.00>Hello <00:02.00>friend\n[00:04.00]Good morning"),
        "test",
        "Test",
        "Test",
    )
    guide = [{"phonetic": "Jelóu frend"}, {"phonetic": "Gud mórning"}]
    adapted = apply_guide(original, guide, bilingual=True)
    assert original["lines"][0]["text"] == "Hello friend"
    assert adapted["lines"][0]["start"] == original["lines"][0]["start"]
    assert adapted["lines"][0]["end"] == original["lines"][0]["end"]
    assert adapted["lines"][0]["words"] == []
    assert adapted["lines"][0]["text"] == "Hello friend"
    assert adapted["lines"][0]["translation"] == "Jelóu frend"
    track = {"id": "test", "title": "Test", "playing": True, "position": 1, "duration": 10}
    AdapterProtocolDecoder().decode(snapshot(track, adapted, 1), observed_at=0)


@pytest.mark.asyncio
async def test_repeated_chorus_requested_once(monkeypatch):
    from singlayer.pronunciation import generate_remote as generate

    calls = []

    async def fake(session, texts):
        calls.extend(texts)
        return [{"phonetic": text + " demo", "tip": ""} for text in texts]

    monkeypatch.setattr("singlayer.pronunciation.request_guide", fake)
    result = await generate({"lines": [{"text": "Hello"}, {"text": "Morning"}, {"text": "Hello"}]})
    assert calls == ["Hello", "Morning"]
    assert result["guide"][0] == result["guide"][2]


@pytest.mark.asyncio
async def test_empty_lines_not_sent_and_bad_batch_split_once(monkeypatch):
    from singlayer.pronunciation import generate_remote as generate

    calls = []

    async def fake(session, texts):
        calls.append(texts)
        if len(texts) > 1:
            raise ValueError("Malformed model JSON")
        return [{"phonetic": "Demo", "tip": ""}]

    monkeypatch.setattr("singlayer.pronunciation.request_guide", fake)
    result = await generate({"lines": [{"text": "Hello"}, {"text": ""}, {"text": "Morning"}]})
    assert calls == [["Hello", "Morning"], ["Hello"], ["Morning"]]
    assert result["guide"][1] == {"phonetic": "", "tip": ""}


def test_local_guide_preserves_spanish_empty_and_repeated_lines():
    pytest.importorskip("espeakng_loader")
    pytest.importorskip("langid")
    from singlayer.pronunciation.local import local_guide

    original = "Canto despacio bajo la lluvia de primavera."
    result = local_guide([original, "", original])
    assert result[0]["phonetic"] == original
    assert result[1] == {"phonetic": "", "tip": ""}
    assert result[2] == result[0]


def test_spanish_reading_handles_multicharacter_phonemes_before_single_letters():
    from singlayer.pronunciation.local import spanish_reading

    assert spanish_reading("ˈtʃaɪld dʒɔɪ ʃuː θɪŋ") == "chái ld yoi shu thing".replace("ái ld", "áild")


def test_short_repeated_english_chorus_uses_song_context():
    pytest.importorskip("espeakng_loader")
    pytest.importorskip("langid")
    from singlayer.pronunciation.local import local_guide

    result = local_guide([
        "I will keep singing with you until the morning comes and we go home together.",
        "Oh honey, honeypie, honey, honey, honeypie",
        "Oh girl, don't you stop",
    ])
    assert all(item["tip"].startswith("Idioma en") for item in result)
    assert result[1]["phonetic"] != "Oh honey, honeypie, honey, honey, honeypie"
