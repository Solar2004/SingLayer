import asyncio
import json
import sys

import pytest

from singlayer.full_track import compile_document, recording_matches, run_command, valid_url, window_positions


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
    assert starts[-1] + 24 >= duration
    assert all(b <= a+24 for a,b in zip(starts, starts[1:]))


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
