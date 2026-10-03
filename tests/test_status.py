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
