import json
from types import SimpleNamespace

import pytest
from aiohttp import web

from singlayer.bridge import Bridge
from singlayer.state import Player


@pytest.mark.asyncio
async def test_status_reports_no_track_and_selected_track():
    bridge = Bridge()
    request = SimpleNamespace(headers={}, host="127.0.0.1:8975")
    response = await bridge.status(request)
    assert json.loads(response.text)["track"] is None
    bridge.store.players[(1, "2")] = Player(
        1,
        "2",
        {
            "title": "Test",
            "artist": "Artist",
            "position": 42,
            "state": 1,
        },
    )
    response = await bridge.status(request)
    assert response.headers["Cache-Control"] == "no-store"
    track = json.loads(response.text)["track"]
    assert track["title"] == "Test"
    assert track["position"] == 42
    assert track["playing"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "headers,host",
    [
        ({"Origin": "https://example.com"}, "127.0.0.1:8975"),
        ({}, "example.com:8975"),
    ],
)
async def test_status_does_not_expose_titles_to_webpages(headers, host):
    with pytest.raises(web.HTTPForbidden):
        await Bridge().status(SimpleNamespace(headers=headers, host=host))


def test_cover_uses_wnp_binary_header_and_bounds_memory():
    bridge = Bridge()
    png = b"\x89PNG\r\n\x1a\n" + b"synthetic-test"
    bridge.receive_cover(7, (42).to_bytes(4, "little") + png)
    assert bridge.covers[(7, "42")][1] == png
    bridge.receive_cover(7, (42).to_bytes(4, "little") + b"not-an-image")
    assert bridge.covers[(7, "42")][1] == png
    for index in range(30):
        bridge.receive_cover(8, index.to_bytes(4, "little") + png)
    assert len(bridge.covers) <= 16


@pytest.mark.asyncio
async def test_active_cover_is_served_only_for_matching_revision():
    bridge = Bridge()
    bridge.store.players[(1, "2")] = Player(1, "2", {"title": "Test", "cover": "browser-cover"})
    png = b"\x89PNG\r\n\x1a\n" + b"synthetic-test"
    bridge.receive_cover(1, (2).to_bytes(4, "little") + png)
    request = SimpleNamespace(headers={}, host="127.0.0.1:8975", query={})
    data = json.loads((await bridge.status(request)).text)
    assert data["api_version"] == 2
    request.query["rev"] = data["track"]["cover"]
    assert (await bridge.cover(request)).body == png
    request.query["rev"] = "stale-revision"
    with pytest.raises(web.HTTPNotFound):
        await bridge.cover(request)
