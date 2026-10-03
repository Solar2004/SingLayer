import asyncio

import pytest
from aiohttp import ClientSession, WSServerHandshakeError
from aiohttp.test_utils import TestServer
from dbus_fast.aio import MessageBus

from singlayer.bridge import HANDSHAKE, Bridge
from singlayer.mpris import OBJECT_PATH, Root
from singlayer.state import FIELDS, PlayerStore, decode_frame


def frame(kind=0, player_id=12, **patch):
    if kind == 0:
        patch = {
            "id": player_id,
            "name": "SoundCloud",
            "title": "Original demo",
            "artist": "SingLayer",
            "album": "",
            "state": 0,
            "position": 10,
            "duration": 180,
            "canSetPosition": 1,
            "canSetState": 1,
            **patch,
        }

    def value(key):
        if key not in patch:
            return ""
        if patch[key] == "":
            return "\x01"
        return str(patch[key]).replace("|", r"\|")

    return f"{kind} {player_id} " + "|".join(value(key) for key in FIELDS) + "|"


def test_sparse_updates_pause_seek_and_clear():
    store = PlayerStore()
    store.apply(1, frame(title="A | B"), now=0)
    assert store.active().data["title"] == "A | B"
    store.apply(1, frame(1, state=1), now=5)
    assert store.active().position(10) == 15
    store.apply(1, frame(1, position=40, artist=""), now=11)
    assert store.active().data["artist"] == ""
    assert store.active().position(20) == 40
    store.apply(1, frame(1, state=0), now=20)
    assert store.active().position(22) == 42


def test_browser_ids_do_not_collide_and_playing_wins():
    store = PlayerStore()
    store.apply(1, frame(title="One"), now=0)
    store.apply(2, frame(title="Two", state=1), now=1)
    assert store.active().data["title"] == "One"
    store.apply(2, frame(1, state=0), now=2)
    assert store.active().data["title"] == "Two"
    store.apply(1, frame(1, position=15), now=3)
    assert store.active().data["title"] == "Two"
    store.remove_connection(2)
    assert store.active().data["title"] == "One"
    store.apply(1, "2 12", now=5)
    assert store.active() is None


def test_stale_clock_does_not_scroll_forever():
    store = PlayerStore()
    store.apply(1, frame(), now=0)
    assert store.active().position(200) == 25


@pytest.mark.parametrize(
    "message", ["bad", "0", "0 x data", "1 4 ||", frame(position="nan"), frame(duration=-1), frame(state=5)]
)
def test_reject_malformed_frames(message):
    with pytest.raises(ValueError):
        decode_frame(message)


async def wait_until(predicate):
    async with asyncio.timeout(3):
        while not predicate():
            await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_websocket_to_real_dbus_and_browser_control():
    """Contract proof: extension wire frames → real D-Bus → confirmed browser seek."""
    bridge = Bridge()
    bus = await MessageBus().connect()
    client_bus = await MessageBus().connect()
    bus.export(OBJECT_PATH, Root())
    bus.export(OBJECT_PATH, bridge.media)
    try:
        async with TestServer(bridge.app()) as server, ClientSession() as session:
            async with session.ws_connect(server.make_url("/"), origin="chrome-extension://test") as ws:
                assert (await ws.receive()).data == HANDSHAKE
                await ws.send_str(frame())
                await wait_until(lambda: bridge.store.active() is not None)
                intro = await client_bus.introspect(bus.unique_name, OBJECT_PATH)
                proxy = client_bus.get_proxy_object(bus.unique_name, OBJECT_PATH, intro)
                properties = proxy.get_interface("org.freedesktop.DBus.Properties")
                values = await properties.call_get_all("org.mpris.MediaPlayer2.Player")
                assert values["Metadata"].value["xesam:title"].value == "Original demo"
                assert values["PlaybackStatus"].value == "Playing"
                player = proxy.get_interface("org.mpris.MediaPlayer2.Player")
                task = asyncio.create_task(
                    player.call_set_position(bridge.store.active().track_id, 30_000_000)
                )
                command = (await ws.receive()).data.split()
                assert command[0] == "12" and command[2:] == ["3", "30"]
                await ws.send_str(f"3 {command[1]} 1")
                await task
                await ws.send_str(frame(1, position=30, state=1))
                await wait_until(lambda: bridge.media.PlaybackStatus == "Paused")
                assert bridge.media.Position == 30_000_000
            await wait_until(lambda: bridge.store.active() is None)
            assert bridge.media.PlaybackStatus == "Stopped"
    finally:
        bus.disconnect()
        client_bus.disconnect()
        await bus.wait_for_disconnect()
        await client_bus.wait_for_disconnect()


@pytest.mark.asyncio
async def test_web_page_origins_are_rejected():
    async with TestServer(Bridge().app()) as server, ClientSession() as session:
        with pytest.raises(WSServerHandshakeError) as error:
            await session.ws_connect(server.make_url("/"), origin="https://example.com")
        assert error.value.status == 403


@pytest.mark.asyncio
async def test_control_rejection_is_reported():
    from dbus_fast import DBusError

    bridge = Bridge()
    async with TestServer(bridge.app()) as server, ClientSession() as session:
        async with session.ws_connect(server.make_url("/")) as ws:
            await ws.receive()
            await ws.send_str(frame())
            await wait_until(lambda: bridge.store.active() is not None)
            task = asyncio.create_task(bridge.command(3, 30, "canSetPosition"))
            command = (await ws.receive()).data.split()
            await ws.send_str(f"3 {command[1]} 2")
            with pytest.raises(DBusError):
                await task
