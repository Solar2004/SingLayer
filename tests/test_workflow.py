import asyncio

import pytest

pytest.importorskip("kotonoha")

from singlayer.workflow import resolve, same_recording, search_candidates, search_identity

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
            if key == "recognize":
                return {"title": TRACK["title"], "artist": TRACK["artist"], "recording_id": "actual"}
            await asyncio.Event().wait()
        finally:
            cancelled.add(key)

    result = await resolve(TRACK, invoke, lambda event: None, audio_allowed=True)
    assert result["document"]["source"] == "lrclib"
    assert result["evidence"]["matches"] == 2
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


@pytest.mark.asyncio
async def test_soundcloud_song_artist_order_retried():
    calls = []

    async def invoke(action, data, timeout):
        calls.append(data)
        if data.get("title") == "Bimbo Doll" and data.get("artist") == "Tila tsoli":
            return {"document": {"source": data["provider"]}}
        return {}

    result = await resolve(
        {
            "title": "Bimbo Doll - Tila tsoli (sped up x nightcore)",
            "artist": "Uploader",
            "source": "SoundCloud",
        },
        invoke,
        lambda e: None,
    )
    assert result["document"]
    assert any(d["title"] == "Bimbo Doll" for d in calls)


def test_decorative_titles_and_uploader_fallback_are_bounded():
    variants = search_candidates(
        {"title": "★ Ｓｉｎｇｅｒ - Ｓｏｎｇ (slowed).mp3", "artist": "Uploader", "source": "SoundCloud"}
    )
    assert len(variants) <= 4
    assert any(v["artist"] == "Singer" and v["title"] == "Song" for v in variants)
    assert any(v["artist"] == "" for v in variants)


def test_recording_id_overrides_similar_names():
    a = {"title": "Demo", "artist": "Singer", "recording_id": "1"}
    assert not same_recording(a, {**a, "recording_id": "2"})
    assert same_recording(a, {**a, "title": "Different display"})


@pytest.mark.asyncio
async def test_soundcloud_metadata_does_not_cancel_audio_consensus():
    calls = []

    async def invoke(action, data, timeout):
        calls.append(action)
        if action == "recognize":
            await asyncio.sleep(0.01)
            return {"title": "True song", "artist": "True singer", "recording_id": "123"}
        return {"document": {"source": data["provider"], "title": data["title"]}}

    result = await resolve({**TRACK, "source": "SoundCloud"}, invoke, lambda e: None, audio_allowed=True)
    assert calls.count("recognize") == 2
    assert result["document"]["title"] == "True song"
    assert result["evidence"] == {"matches": 2, "samples": 2, "confirmed": True}


@pytest.mark.asyncio
async def test_conflicting_samples_are_not_confirmed_and_all_three_tried():
    count = 0

    async def invoke(action, data, timeout):
        nonlocal count
        if action == "recognize":
            count += 1
            return {"title": f"Song {count}", "artist": "Singer", "recording_id": str(count)}
        return {"document": {"source": data["provider"]}}

    result = await resolve({**TRACK, "source": "SoundCloud"}, invoke, lambda e: None, audio_allowed=True)
    assert count == 3
    assert not result["evidence"]["confirmed"]


@pytest.mark.parametrize("title,artist,expected", [
    ("night changes (Sped Up)", "andie._", ("night changes", "")),
    ("night dancer - imase (sped up)", "altvile", ("night dancer", "imase")),
    ("𝔗𝔥𝔢𝔪 𝔠𝔥𝔞𝔫𝔤𝔢𝔰 - 𝔱𝔥𝔲𝔫𝔡𝔢𝔯𝔠𝔞𝔱 (𝔰𝔭𝔢𝔡 𝔲𝔭)", "KISMET", ("Them changes", "thundercat")),
    ("After Dark - Mr.Kitty (Slowed, pitched down and extra reverb)", "Transmission", ("After Dark", "Mr.Kitty")),
    ("mr.kitty - after dark (slowed+reverb+muffled)", "idk anymore", ("after dark", "mr.kitty")),
    ("Artist - Song speed up", "uploader", ("Song", "Artist")),
])
def test_observed_soundcloud_variants(title, artist, expected):
    track = {"title": title, "artist": artist, "source": "SoundCloud", "duration": 300}
    candidates = search_candidates(track)
    assert any((c["title"].casefold(), c["artist"].casefold()) == tuple(x.casefold() for x in expected) for c in candidates)
    assert search_identity(track)["edited"]
    assert all(c.get("duration") is None for c in candidates)
@pytest.mark.parametrize("title", ["Slow Dancing in the Dark", "Dancing Slow", "The Remix Song"])
def test_catalog_cleaning_preserves_legitimate_titles(title):
    from singlayer.workflow import catalog_text

    assert catalog_text(title) == title


@pytest.mark.asyncio
async def test_recognized_edit_finds_original_lyrics_without_claiming_identity():
    calls = []

    async def invoke(action, data, timeout):
        calls.append((action, data))
        if action == "recognize":
            return {"title": "Honeypie (Slowed + Bass Boosted)", "artist": "Thorstentekk", "recording_id": "edit-123"}
        if data.get("title") == "Honeypie" and data.get("artist") == "":
            return {"document": {"source": "lrclib", "title": "Honeypie", "artist": "JAWNY"}}
        return {}

    result = await resolve(
        {"title": "Honeypie (Slowed + Bass Boosted)", "artist": "VYRUS", "source": "SoundCloud"},
        invoke, lambda e: None, recognize=True, audio_allowed=True,
    )
    assert result["document"]["artist"] == "JAWNY"
    assert result["recognized"]["recording_id"] == "edit-123"
    assert result["evidence"]["recognition_confirmed"]
    assert not result["evidence"]["confirmed"]
    assert sum(action == "recognize" for action, _ in calls) == 2


@pytest.mark.asyncio
async def test_confirmed_recording_survives_missing_lyrics():
    async def invoke(action, data, timeout):
        if action == "recognize":
            return {"title": "Unknown song", "artist": "Singer", "recording_id": "123"}
        return {}

    result = await resolve(TRACK, invoke, lambda e: None, recognize=True, audio_allowed=True)
    assert result["recognized"]["recording_id"] == "123"
    assert result["evidence"]["recognition_confirmed"]
    assert "document" not in result


@pytest.mark.parametrize("title,expected", [
    ("mr kitty | after dark | slowed + reverbed", ("after dark", "mr kitty")),
    ("Honeypie - bass boosted", ("Honeypie", "")),
    ("After Dark [8D Audio]", ("After Dark", "")),
    ("NIGHT DANCER (0.8x)", ("NIGHT DANCER", "")),
    ("Artist - Song slowed to perfection", ("Song", "Artist")),
    ("after dark slowed reverb // tiktok version", ("after dark", "")),
])
def test_additional_real_world_edit_notations(title, expected):
    track = {"title": title, "artist": "Uploader", "source": "SoundCloud", "duration": 300}
    candidates = search_candidates(track)
    assert any(tuple(value.casefold() for value in (c["title"], c["artist"])) ==
               tuple(value.casefold() for value in expected) for c in candidates)
    assert search_identity(track)["edited"]
    assert all(c.get("duration") is None for c in candidates)


@pytest.mark.asyncio
async def test_missing_artist_waits_for_audio_even_when_metadata_catalog_hits():
    recognized = {"title": "Real song", "artist": "Real artist", "recording_id": "actual"}
    calls = []

    async def invoke(action, data, timeout):
        calls.append((action, data.get("artist")))
        if action == "recognize":
            await asyncio.sleep(.01)
            return recognized
        return {"document": {"source": "lrclib", "title": data["title"]}}

    result = await resolve({**TRACK, "artist": ""}, invoke, lambda event: None, audio_allowed=True)
    assert result["recognized"] == recognized
    assert result["evidence"]["matches"] == 2
    assert result["document"]["title"] == "Real song"
