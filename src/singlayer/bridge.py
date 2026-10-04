"""Local WebNowPlaying WebSocket adapter with an MPRIS output."""

import asyncio
import hashlib
import json
import logging
import signal
import time
from contextlib import suppress
from urllib.parse import urlsplit

from aiohttp import WSMsgType, web
from dbus_fast import DBusError
from dbus_fast.aio import MessageBus
from dbus_fast.constants import NameFlag, RequestNameReply

from .artwork import safe_cover_url
from .mpris import BUS_NAME, OBJECT_PATH, MediaPlayer, Root
from .source_link import matching_source, source_message
from .state import PlayerStore

LOG = logging.getLogger(__name__)
HANDSHAKE = "ADAPTER_VERSION 3.0.0;WNPLIB_REVISION 3"


class Bridge:
    def __init__(self):
        self.store = PlayerStore()
        self.media = MediaPlayer(self.store, self.command)
        self.connections: dict[int, web.WebSocketResponse] = {}
        self.pending: dict[tuple[int, int], asyncio.Future] = {}
        self.connection_id = 0
        self.command_id = 0
        self.covers = {}
        self.browser_families = {}
        self.source_connections = {}

    def receive_cover(self, connection, data):
        if not 12 < len(data) <= 1_500_000:
            return
        body = data[4:]
        if not (body.startswith(b"\x89PNG\r\n\x1a\n") or body.startswith(b"\xff\xd8\xff")):
            return
        key = connection, str(int.from_bytes(data[:4], "little"))
        if len(self.covers) >= 16 and key not in self.covers:
            self.covers.pop(next(iter(self.covers)))
        self.covers[key] = (hashlib.sha256(body).hexdigest()[:20], body)

    async def command(self, kind, value, capability):
        player = self.store.active()
        if not player or not player.data.get(capability):
            raise DBusError("org.mpris.MediaPlayer2.NotSupported", "Player does not support this control")
        connection = player.connection
        ws = self.connections.get(connection)
        if ws is None or ws.closed:
            raise DBusError("org.mpris.MediaPlayer2.Failed", "Browser disconnected")
        if kind == 3 and player.data.get("duration", 0) > 0:
            value = min(value, player.data["duration"])
        self.command_id += 1
        key = connection, self.command_id
        future = asyncio.get_running_loop().create_future()
        self.pending[key] = future
        try:
            await ws.send_str(f"{player.browser_id} {key[1]} {kind} {int(value)}")
            result = await asyncio.wait_for(future, 4)
            if result != 1:
                raise DBusError("org.mpris.MediaPlayer2.Failed", "Browser rejected the control")
        except (TimeoutError, ConnectionError) as exc:
            raise DBusError("org.mpris.MediaPlayer2.Failed", "Browser did not confirm the control") from exc
        finally:
            self.pending.pop(key, None)

    async def websocket(self, request):
        # Website JavaScript must not be able to impersonate the extension.
        origin = request.headers.get("Origin")
        if origin and urlsplit(origin).scheme not in {"chrome-extension", "moz-extension"}:
            raise web.HTTPForbidden(text="Only browser extensions may connect")
        ws = web.WebSocketResponse(heartbeat=15, max_msg_size=2 * 1024 * 1024)
        await ws.prepare(request)
        self.connection_id += 1
        connection = self.connection_id
        self.connections[connection] = ws
        ua = request.headers.get("User-Agent", "")
        self.browser_families[connection] = (
            "Firefox" if "Firefox/" in ua else "Edge" if "Edg/" in ua else "Chromium"
        )
        await ws.send_str(HANDSHAKE)
        LOG.info("Browser adapter connected (%s)", connection)
        try:
            async for message in ws:
                if message.type == WSMsgType.BINARY:
                    self.receive_cover(connection, message.data)
                    continue
                if message.type != WSMsgType.TEXT:
                    continue  # Artwork binary frames aren't needed by the lyrics engine.
                before = self.media.Position
                previous = self.store.active()
                old_track = previous.track_id if previous else None
                try:
                    if message.data.startswith("3 "):
                        _, event_id, status = message.data.split()
                        future = self.pending.get((connection, int(event_id)))
                        if future is not None and not future.done():
                            future.set_result(int(status))
                        continue
                    self.store.apply(connection, message.data)
                except (ValueError, TypeError):
                    LOG.warning("Rejected malformed browser frame")
                    continue
                current = self.store.active()
                new_track = current.track_id if current else None
                self.media.publish(
                    seeked=old_track != new_track or abs(self.media.Position - before) > 1_500_000
                )
        finally:
            self.connections.pop(connection, None)
            self.browser_families.pop(connection, None)
            self.covers = {key: value for key, value in self.covers.items() if key[0] != connection}
            self.store.remove_connection(connection)
            for (owner, _), future in self.pending.items():
                if owner == connection and not future.done():
                    future.set_exception(ConnectionError("Browser disconnected"))
            self.media.publish()
            LOG.info("Browser adapter disconnected (%s)", connection)
        return ws

    async def source_socket(self, request):
        origin = request.headers.get("Origin", "")
        if urlsplit(origin).scheme not in {"chrome-extension", "moz-extension"}:
            raise web.HTTPForbidden(text="Only browser extensions may connect")
        ws = web.WebSocketResponse(heartbeat=15, max_msg_size=4096)
        await ws.prepare(request)
        entries = {}
        self.source_connections[ws] = entries
        try:
            async for message in ws:
                if message.type != WSMsgType.TEXT:
                    continue
                try:
                    value = json.loads(message.data)
                    for old in list(entries):
                        if time.monotonic() - entries[old]["at"] >= 8:
                            del entries[old]
                    tab = value["tab"]
                    if not isinstance(tab, int) or len(entries) >= 32 and tab not in entries:
                        raise ValueError("Invalid source tab")
                    entries[tab] = source_message(value)
                except (ValueError, KeyError, TypeError, AttributeError):
                    continue
        finally:
            self.source_connections.pop(ws, None)
        return ws

    async def health(self, request):
        return web.json_response(
            {"service": "singlayer", "browsers": len(self.connections), "players": len(self.store.players)}
        )

    async def shutdown(self, app):
        for ws in list(self.connections.values()) + list(self.source_connections):
            await ws.close(code=1001, message=b"SingLayer stopping")

    async def status(self, request):
        self.local_request(request)
        player = self.store.active()
        cover = self.covers.get((player.connection, player.browser_id)) if player else None
        return web.json_response(
            {
                "service": "singlayer",
                "browsers": len(self.connections),
                "browser_families": list(self.browser_families.values()),
                "api_version": 2,
                "track": None
                if player is None
                else {
                    "title": player.data.get("title", ""),
                    "id": player.track_id,
                    "source": player.data.get("name", ""),
                    "url": matching_source([entry for entries in self.source_connections.values() for entry in entries.values()], player),
                    "cover": cover[0] if cover and player.data.get("cover") else None,
                    "cover_url": safe_cover_url(player.data.get("cover")),
                    "artist": player.data.get("artist", ""),
                    "position": player.position(time.monotonic()),
                    "duration": player.data.get("duration", 0),
                    "playing": player.data.get("state") == 0,
                    "stale": time.monotonic() - player.position_observed > 15,
                },
            },
            headers={"Cache-Control": "no-store"},
        )

    @staticmethod
    def local_request(request):
        if request.headers.get("Origin") or request.host not in {"127.0.0.1:8975", "localhost:8975"}:
            raise web.HTTPForbidden()

    async def cover(self, request):
        self.local_request(request)
        player = self.store.active()
        cover = self.covers.get((player.connection, player.browser_id)) if player else None
        if not cover or request.query.get("rev") != cover[0]:
            raise web.HTTPNotFound()
        body = cover[1]
        return web.Response(
            body=body,
            content_type="image/png" if body.startswith(b"\x89PNG") else "image/jpeg",
            headers={"Cache-Control": "no-store"},
        )

    def app(self):
        app = web.Application()
        app.router.add_get("/", self.websocket)
        app.router.add_get("/source", self.source_socket)
        app.router.add_get("/health", self.health)
        app.router.add_get("/status", self.status)
        app.router.add_get("/cover", self.cover)
        app.on_shutdown.append(self.shutdown)
        return app


async def serve(port=8975):
    bridge = Bridge()
    bus = await MessageBus().connect()
    runner = web.AppRunner(bridge.app(), access_log=None)
    try:
        reply = await bus.request_name(BUS_NAME, NameFlag.DO_NOT_QUEUE)
        if reply != RequestNameReply.PRIMARY_OWNER:
            raise RuntimeError("SingLayer is already running")
        bus.export(OBJECT_PATH, Root())
        bus.export(OBJECT_PATH, bridge.media)
        await runner.setup()
        await web.TCPSite(runner, "127.0.0.1", port).start()
        LOG.info("WebNowPlaying custom adapter: ws://127.0.0.1:%s", port)
        stop = asyncio.Event()
        for sig in (signal.SIGINT, signal.SIGTERM):
            asyncio.get_running_loop().add_signal_handler(sig, stop.set)
        await stop.wait()
    finally:
        await runner.cleanup()
        bus.disconnect()
        with suppress(Exception):
            await bus.wait_for_disconnect()
