"""Optional integration against the actual pinned upstream MPRIS consumer."""

import pytest
from dbus_fast.aio import MessageBus
from test_bridge import frame

from singlayer.bridge import Bridge
from singlayer.mpris import OBJECT_PATH, Root


@pytest.mark.asyncio
async def test_upstream_reads_browser_track_and_clock():
    module = pytest.importorskip("kotonoha.providers.mpris_session")
    bridge = Bridge()
    bridge.store.apply(1, frame(state=1, position=42))
    publisher = await MessageBus().connect()
    reader = await MessageBus().connect()
    try:
        publisher.export(OBJECT_PATH, Root())
        publisher.export(OBJECT_PATH, bridge.media)
        session = module.MprisSession(bus=reader)
        player = await session.player(publisher.unique_name)
        assert player is not None
        track = await session.track(player)
        assert track.title == "Original demo"
        assert track.artist == "SingLayer"
        assert track.length_s == 180
        assert await session.position(player) == 42
        assert await session.status(player) == "Paused"
    finally:
        publisher.disconnect()
        reader.disconnect()
        await publisher.wait_for_disconnect()
        await reader.wait_for_disconnect()
