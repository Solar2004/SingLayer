import asyncio
import json
import sys

import pytest

from singlayer.full_track import (
    FULL_WINDOW,
    compile_document,
    recording_matches,
    run_command,
    valid_url,
    window_positions,
)


@pytest.mark.parametrize('url', ['https://soundcloud.com/artist/song', 'https://www.youtube.com/watch?v=abc',
                                 'https://youtu.be/abc', 'https://artist.bandcamp.com/track/song'])
def test_exact_public_music_urls(url):
    assert valid_url(url) == url


@pytest.mark.parametrize('url', ['http://soundcloud.com/a/b', 'https://soundcloud.com.evil.test/a',
                                 'https://127.0.0.1/', 'file:///tmp/audio', 'https://user:pass@youtube.com/watch?v=x'])
def test_invalid_or_private_url_rejected(url):
    with pytest.raises(ValueError):
        valid_url(url)


def test_wrong_version_or_playlist_never_applied():
    track = {'title': 'Song ULTRA SLOWED', 'duration': 192}
    assert recording_matches({'title': track['title'], 'duration': 192}, track) == 192
    for info in ({'title': track['title'], 'duration': 134}, {'title': 'Different song', 'duration': 192},
                 {'title': track['title'], 'duration': 192, 'entries': []},
                 {'title': track['title'], 'duration': 192, 'is_live': True}):
        with pytest.raises(ValueError):
            recording_matches(info, track)


@pytest.mark.parametrize('duration', [4, 24, 25, 177.34, 192, 900])
def test_all_audio_including_last_second_is_covered(duration):
    starts = window_positions(duration)
    assert starts[0] == 0
    assert starts[-1] + FULL_WINDOW >= duration
    assert all(b <= a+FULL_WINDOW for a,b in zip(starts, starts[1:]))


def test_catalog_corrects_only_unique_text_without_moving_audio_clock_and_remix_preserves_raw():
    raw = {'lines': [{'text': 'First original phrase with one wrong word', 'start': 42, 'end': 45, 'words': []}]}
    cat = {'lines': [{'text': 'First original phrase with one clear word', 'start': 5, 'end': 9}]}
    doc = compile_document(raw, cat)
    assert doc['lines'][0]['start'] == 42
    assert doc['lines'][0]['end'] == 45
    assert doc['lines'][0]['text'] == cat['lines'][0]['text']
    assert compile_document(raw, cat, 'transcript')['lines'][0]['text'] == raw['lines'][0]['text']
    assert compile_document(None, cat) is None


@pytest.mark.asyncio
async def test_bounded_subprocess_is_cancelled_and_reaped(tmp_path):
    marker = tmp_path/'pid.json'
    code = 'import os,json,time;open(' + repr(str(marker)) + ',"w").write(json.dumps(os.getpid()));time.sleep(30)'
    task = asyncio.create_task(run_command([sys.executable, '-c', code], timeout=30))
    for _ in range(100):
        if marker.exists():
            break
        await asyncio.sleep(.01)
    import os
    pid = json.loads(marker.read_text())
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_playhead_priority_preserves_full_coverage():
    from singlayer.full_track import next_window

    remaining = window_positions(177.34)
    original = set(remaining)
    chosen = []
    while remaining:
        start = next_window(remaining, 70)
        remaining.remove(start)
        chosen.append(start)
    assert chosen[0] == 64
    assert set(chosen) == original
    assert next_window([0, 16, 32], 100) == 0
    assert next_window([32, 48], 2) == 32


def test_exact_cache_reuses_audio_with_new_catalog_but_not_wrong_model_or_version(tmp_path):
    from singlayer.full_track import cached_result

    raw = {'lines': [{'text': 'First original phrase with one wrong word', 'start': 42, 'end': 45, 'words': []}]}
    result = {'url': 'https://soundcloud.com/a/b', 'title': 'Song remix', 'duration': 80,
              'engine': 'whisper.cpp', 'engine_signature': 'model-sha', 'raw_document': raw, 'document': raw}
    (tmp_path/'cache.json').write_text(json.dumps(result))
    data = {**result, 'track': {'title': 'Song remix', 'duration': 80}, 'route': 'alignment',
            'catalog': {'lines': [{'text': 'First original phrase with one clear word'}]}}
    hit = cached_result(tmp_path, data)
    assert hit['document']['lines'][0]['text'] == data['catalog']['lines'][0]['text']
    assert hit['raw_document']['lines'][0]['text'] == raw['lines'][0]['text']
    assert cached_result(tmp_path, {**data, 'engine_signature': 'another-model'}) is None
    assert cached_result(tmp_path, {**data, 'track': {'title': 'Song remix', 'duration': 120}}) is None
    import os
    os.utime(tmp_path/'cache.json', (0, 0))
    assert cached_result(tmp_path, data) is None


@pytest.mark.asyncio
async def test_progressive_result_precedes_completion_and_replay_needs_no_network(monkeypatch, tmp_path):
    from singlayer import full_track as full

    monkeypatch.setenv('XDG_CACHE_HOME', str(tmp_path))
    calls, events = [], []
    duration = 80
    async def command(argv, **kwargs):
        if '--dump-single-json' in argv:
            return json.dumps({'id': 'exact', 'title': 'Song remix', 'duration': duration}).encode()
        if '--load-info-json' in argv:
            from pathlib import Path
            Path(argv[argv.index('-o')+1].replace('%(ext)s', 'ogg')).write_bytes(b'audio')
            return b''
        assert argv[0] == 'ffmpeg'
        return bytes(duration*32000)
    class Health:
        status = 200
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def json(self):
            return {'service': 'singlayer-transcription', 'ready': True, 'busy': False, 'backend': 'whisper.cpp'}
    class Session:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        def get(self, *args): return Health()
    async def transcribe(audio, start):
        calls.append(start)
        if len(calls) == 2:
            assert any('full_partial' in event for event in events)
            assert not any('full_result' in event for event in events)
        return {'lines': [{'text': f'Measured phrase at {start}', 'start': start+2, 'end': start+4, 'words': []}]}
    monkeypatch.setattr(full, 'run_command', command)
    monkeypatch.setattr(full.shutil, 'which', lambda name: name)
    monkeypatch.setattr(full.aiohttp, 'ClientSession', lambda **kwargs: Session())
    monkeypatch.setattr(full, 'transcribe_window', transcribe)
    data = {'url': 'https://soundcloud.com/a/b', 'track': {'title': 'Song remix', 'duration': 80, 'position': 48},
            'engine': 'whisper.cpp', 'route': 'transcript'}
    await full.analyze(data, events.append)
    assert calls[0] == 48
    assert set(calls) == set(window_positions(duration))
    assert events[-1]['full_result']['duration'] == duration
    async def forbidden(*args, **kwargs):
        raise AssertionError('A replay must not download or transcribe again')
    monkeypatch.setattr(full, 'run_command', forbidden)
    monkeypatch.setattr(full, 'transcribe_window', forbidden)
    replay = []
    await full.analyze(data, replay.append)
    assert replay[0]['cached'] is True


@pytest.mark.asyncio
async def test_actual_playhead_honors_seek_pause_and_rejects_another_track(monkeypatch):
    from singlayer import full_track as full

    payload = {'service': 'singlayer', 'track': {'id': 'current', 'position': 90, 'playing': False, 'stale': False}}
    class Response:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        def raise_for_status(self): pass
        @property
        def content(self): return self
        async def read(self, limit): return json.dumps(payload).encode()
    class Session:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        def get(self, *args, **kwargs): return Response()
    monkeypatch.setattr(full.aiohttp, 'ClientSession', lambda **kwargs: Session())
    assert await full.current_playhead({'id': 'current'}, (20, True), 100) == (90, False)
    assert await full.current_playhead({'id': 'another'}, (20, True), 100) == (20, True)
    payload['track']['position'] = float('nan')
    assert await full.current_playhead({'id': 'current'}, (20, True), 100) == (20, True)
