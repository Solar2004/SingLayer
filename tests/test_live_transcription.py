import pytest

from singlayer.alignment import align_fragment, unique_match
from singlayer.live_transcription import audible, continuous, merge_transcript, wav_window
from singlayer.transcription import transcript_document

TRACK = {"title": "Original test", "id": "one", "position": 20, "playing": True, "stale": False}


def test_pause_seek_track_and_clock_changes_invalidate_audio():
    assert continuous(TRACK, {**TRACK, "position": 21}, 1)
    for change in ({"playing": False}, {"stale": True}, {"id": "other"}, {"position": 60}, {"position": 0}):
        assert not continuous(TRACK, {**TRACK, **change}, .4)
    assert not continuous(TRACK, None, .4)


def test_overlap_replaced_without_duplicate_text_and_memory_bounded():
    old = transcript_document({"words": [{"start": 0, "end": 3, "word": "hello demo"}]}, 0, 12)
    new = transcript_document({"words": [{"start": 0, "end": 3, "word": "hello demo"}]}, 2, 12)
    merged = merge_transcript(old, new)
    assert len(merged["lines"]) == 1
    assert merged["lines"][0]["start"] == 2
    for n in range(520):
        merged = merge_transcript(merged, transcript_document(
            {"words": [{"start": 0, "end": 1, "word": str(n)}]}, 10 + n * 3, 12))
    assert len(merged["lines"]) == 512
    assert merged["lines"][0]["index"] == 0


def test_silence_filtered_and_wav_is_valid():
    import io
    import wave

    assert not audible(bytes(32000))
    pcm = b"\xff\x3f" * 16000
    assert audible(pcm)
    with wave.open(io.BytesIO(wav_window(pcm))) as wav:
        assert wav.getframerate() == 16000
        assert wav.getnframes() == 16000


def line(text, start, end):
    return {"text": text, "start": start, "end": end, "words": [], "translation": ""}


def test_repeated_chorus_and_short_phrases_do_not_auto_align():
    chorus = "original chorus with several distinctive words"
    lines = [line(chorus, 0, 4), line("another verse for this original example", 5, 9), line(chorus, 20, 24)]
    assert unique_match(chorus, lines) is None
    assert unique_match("with several", lines) is None


def test_japanese_matching_requires_distinctive_phrase():
    phrase = "静かな夜に星が輝いている"
    assert unique_match(phrase, [line(phrase, 0, 4)]) == (0, 1, 1)
    assert unique_match("夜に", [line(phrase, 0, 4)]) is None


@pytest.mark.asyncio
async def test_early_playback_change_is_normal_discontinuity(monkeypatch):
    from singlayer import live_transcription as live

    async def changed(*args):
        raise live.PlaybackChanged()

    monkeypatch.setattr(live, "_run_live", changed)
    events = []
    await live.run_live({"track": TRACK}, events.append)
    assert events == [{"discontinuity": True}]


@pytest.mark.parametrize("speed", [.65, .8, 1, 1.25, 1.7])
def test_piecewise_alignment_follows_speed_and_reordered_sections(speed):
    first = "original first verse with seven distinct words"
    second = "later passage about rain over distant hills"
    catalog = {"lines": [line(first, 0, 4), line(second, 20, 24)]}
    # The later verse plays first, then a cut returns to the opening verse.
    transcript = {"lines": [line(second, 30, 30 + 4 / speed), line(first, 50, 50 + 4 / speed)]}
    aligned = align_fragment(transcript, catalog)
    assert [x["text"] for x in aligned["lines"]] == [second, first]
    assert aligned["lines"][0]["start"] == 30
    assert aligned["lines"][1]["end"] == pytest.approx(50 + 4 / speed)
    assert aligned["timing"] == "Line"
    assert catalog["lines"][0]["start"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_first", [False, True])
async def test_live_cancellation_reaps_capture_and_bounds_pending_audio(monkeypatch, invalid_first):
    import asyncio

    from singlayer import live_transcription as live

    monkeypatch.setattr(live, "RATE", 16)
    monkeypatch.setattr(live, "WINDOW", 2)
    monkeypatch.setattr(live, "HOP", 1)
    observed = {"status": 0, "terminated": False, "cancelled": False, "inferences": 0}
    events = []

    class Response:
        status = 200
        def __init__(self, url):
            self.url = url
            self.content = self
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        def raise_for_status(self):
            pass
        async def read(self, size):
            import json
            if self.url.endswith("/health"):
                return json.dumps({"service": "singlayer-crisperwhisper", "ready": True}).encode()
            observed["status"] += 1
            return json.dumps({"service": "singlayer", "track": {
                **TRACK, "playing": observed["status"] < 3,
            }}).encode()

    class Session:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        def get(self, url, **kwargs):
            return Response(url)

    class Process:
        returncode = None
        def __init__(self):
            self.stdout = self
        async def readexactly(self, size):
            await asyncio.sleep(.01)
            return b"\xff\x3f" * (size // 2)
        def terminate(self):
            observed["terminated"] = True
            self.returncode = 0
        async def wait(self):
            return self.returncode

    async def spawn(*args, **kwargs):
        assert "parec" == args[0]
        return Process()

    async def target(*args):
        return {"index": 1, "device": "browser.monitor"}

    async def infer(*args):
        observed["inferences"] += 1
        if invalid_first and observed["inferences"] == 1:
            raise ValueError("Whisper devolvió tiempos fuera del fragmento")
        try:
            await asyncio.Event().wait()
        finally:
            observed["cancelled"] = True

    monkeypatch.setattr(live.aiohttp, "ClientSession", Session)
    monkeypatch.setattr(live.asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr("singlayer.worker.audio_target", target)
    monkeypatch.setattr(live, "transcribe_window", infer)
    await asyncio.wait_for(live.run_live({"track": TRACK}, events.append), 2)
    assert observed["terminated"] and observed["cancelled"]
    assert observed["inferences"] == (2 if invalid_first else 1)
    if invalid_first:
        assert any("incierto" in event.get("live_status", "") for event in events)
    assert any("descartando" in event.get("live_status", "") for event in events)
    assert {"discontinuity": True} in events
    assert not any("transcript" in event for event in events)


def test_exact_catalog_match_retains_measured_words():
    text = "original verse with many distinctive words"
    words = [{"text": text, "start": 50, "end": 54}]
    catalog = {"lines": [line(text, 10, 14)]}
    transcript = {"lines": [{**line(text, 50, 54), "words": words}]}
    aligned = align_fragment(transcript, catalog)
    assert aligned["timing"] == "Word"
    assert aligned["lines"][0]["words"] == words
    assert aligned["lines"][0]["words"] is not words
