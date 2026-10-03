import asyncio

import pytest

pytest.importorskip("kotonoha")

from singlayer.workflow import resolve, search_identity

TRACK = {"title": "Original demo", "artist": "Singer", "duration": 180}


def test_soundcloud_search_identity_keeps_raw_and_ignores_remix_duration():
    raw = {"title": "Stromae - Alors On Danse (Slowed_TikTok Remix)", "artist": "Uploader", "duration": 313}
    result = search_identity(raw)
    assert result["artist"] == "Stromae"
    assert result["duration"] is None
    assert result["edited"]
    assert raw["artist"] == "Uploader"
    assert result["title"] == "Alors On Danse"


def test_manual_artist_and_dash_title_are_not_reinterpreted():
    raw = {"title": "A - B", "artist": "Original singer", "manual": True}
    assert search_identity(raw)["artist"] == "Original singer"


@pytest.mark.asyncio
async def test_native_and_audio_overlap_and_losers_are_cancelled():
    entered, cancelled = set(), set()
    barrier = asyncio.Event()

    async def invoke(action, data, timeout):
        key = data.get("provider", action)
        entered.add(key)
        if len(entered) == 4:
            barrier.set()
        try:
            await asyncio.wait_for(barrier.wait(), 1)
            if key == "lrclib":
                return {"document": {"source": "lrclib"}}
            await asyncio.Event().wait()
        finally:
            cancelled.add(key)

    result = await resolve(TRACK, invoke, lambda event: None, audio_allowed=True)
    assert result["document"]["source"] == "lrclib"
    assert entered == {"lrclib", "netease", "kugou", "recognize"}
    assert cancelled == entered


@pytest.mark.asyncio
async def test_no_capture_without_permission_and_plain_is_not_timed():
    events, calls = [], []

    async def invoke(action, data, timeout):
        calls.append(action)
        return {"plain": "Original test text"} if data["provider"] == "Genius" else {}

    result = await resolve(TRACK, invoke, events.append)
    assert "recognize" not in calls
    assert "document" not in result
    assert result["plain"] == "Original test text"
    assert any(e["stage"] == "shazam" and e["state"] == "skipped" for e in events)


@pytest.mark.asyncio
async def test_three_samples_max_and_identical_recognition_deduplicates_queries():
    calls = []

    async def invoke(action, data, timeout):
        calls.append((action, data))
        if action == "recognize":
            return {"title": "Recognized", "artist": "Singer"}
        return {}

    await resolve(TRACK, invoke, lambda e: None, recognize=True, audio_allowed=True)
    assert sum(action == "recognize" for action, _ in calls) == 3
    assert sum(data.get("provider") == "lrclib" for _, data in calls) == 1


@pytest.mark.asyncio
async def test_missing_engine_stops_capture_retries():
    calls, events = [], []

    async def invoke(action, data, timeout):
        calls.append(action)
        return {"missing": True, "error": "Missing engine"} if action == "recognize" else {}

    await resolve(TRACK, invoke, events.append, audio_allowed=True)
    assert calls.count("recognize") == 1
    assert any(e["state"] == "missing" for e in events)


@pytest.mark.asyncio
async def test_cancelled_track_cancels_every_operation():
    active = set()
    ready = asyncio.Event()

    async def invoke(action, data, timeout):
        key = data.get("provider", action)
        active.add(key)
        if len(active) == 4:
            ready.set()
        try:
            await asyncio.Event().wait()
        finally:
            active.remove(key)

    task = asyncio.create_task(resolve(TRACK, invoke, lambda e: None, audio_allowed=True))
    await asyncio.wait_for(ready.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not active
