import asyncio
import json
from types import SimpleNamespace

import pytest
from aiohttp import ClientSession, WSServerHandshakeError
from aiohttp.test_utils import TestServer

from singlayer.bridge import Bridge
from singlayer.source_link import matching_source, source_message

VALUE = {'tab': 1, 'url': 'https://soundcloud.com/singer/song', 'title': 'Song', 'duration': 180}


def test_source_requires_current_matching_unambiguous_recording():
    entry = source_message(VALUE)
    player = SimpleNamespace(data={'title': 'Song', 'duration': 180})
    assert matching_source([entry], player) == VALUE['url']
    assert matching_source([{**entry, 'at': entry['at']-9}], player) is None
    assert matching_source([entry], SimpleNamespace(data={'title': 'Other', 'duration': 180})) is None
    assert matching_source([entry], SimpleNamespace(data={'title': 'Song', 'duration': 200})) is None
    assert matching_source([entry, {**entry, 'url': 'https://soundcloud.com/singer/another'}], player) is None
    assert matching_source([entry], SimpleNamespace(data={'title': '𝑺𝒐𝒏𝒈', 'duration': 180})) == VALUE['url']


@pytest.mark.parametrize('patch', [
    {'url': 'http://localhost/song'}, {'url': 'https://soundcloud.com/you/history'},
    {'url': 'https://soundcloud.com@evil.test/singer/song'}, {'duration': float('nan')},
    {'duration': 901}, {'duration': True}, {'title': ''}, {'url': 'https://www.youtube.com/playlist?v=x'},
])
def test_reject_nonrecording_sources(patch):
    with pytest.raises(ValueError):
        source_message({**VALUE, **patch})


@pytest.mark.asyncio
async def test_extension_source_socket_and_disconnect_cleanup():
    bridge = Bridge()
    async with TestServer(bridge.app()) as server, ClientSession() as session:
        for origin in (None, 'https://soundcloud.com'):
            with pytest.raises(WSServerHandshakeError):
                await session.ws_connect(server.make_url('/source'), origin=origin)
        async with session.ws_connect(server.make_url('/source'), origin='chrome-extension://test') as ws:
            await ws.send_str(json.dumps(VALUE))
            async with asyncio.timeout(2):
                while not any(bridge.source_connections.values()):
                    await asyncio.sleep(.01)
            entry = next(iter(next(iter(bridge.source_connections.values())).values()))
            assert entry['url'] == VALUE['url']
        async with asyncio.timeout(2):
            while bridge.source_connections:
                await asyncio.sleep(.01)
