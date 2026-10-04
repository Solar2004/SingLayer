import json
import sys

import pytest

from singlayer.worker import command, recognize


@pytest.mark.asyncio
async def test_subprocess_json_and_output_limit():
    out = await command([sys.executable, "-c", "import json; print(json.dumps({'ok': True}))"])
    assert json.loads(out)["ok"]
    with pytest.raises(ValueError, match="grande"):
        await command([sys.executable, "-c", "print('x' * 5000)"], limit=100)


@pytest.mark.asyncio
async def test_subprocess_timeout_is_bounded():
    with pytest.raises(TimeoutError):
        await command([sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.05)


@pytest.mark.asyncio
async def test_missing_recognizer_never_opens_capture(monkeypatch):
    monkeypatch.setattr("singlayer.worker.Path.is_file", lambda self: False)
    monkeypatch.setattr("singlayer.worker.shutil.which", lambda name: None)
    monkeypatch.setattr("singlayer.worker.importlib.util.find_spec", lambda name: None)
    called = []

    async def capture(*args, **kwargs):
        called.append(True)

    monkeypatch.setattr("singlayer.worker.command", capture)
    result = await recognize()
    assert result["missing"]
    assert not called


@pytest.mark.asyncio
async def test_capture_never_defaults_to_microphone(monkeypatch):
    monkeypatch.setattr("singlayer.worker.shutil.which", lambda name: f"/usr/bin/{name}")
    calls = []

    async def target(title):
        return {"index": 41, "device": "speaker.monitor"}

    async def sample(target):
        assert target["index"] == 41
        return b"fixture-wav"

    async def capture(argv, **kwargs):
        calls.append(argv)
        return json.dumps({"track": {"title": "Demo", "subtitle": "Singer"}}).encode()

    monkeypatch.setattr("singlayer.worker.audio_target", target)
    monkeypatch.setattr("singlayer.worker.browser_sample", sample)
    monkeypatch.setattr("singlayer.worker.command", capture)
    result = await recognize()
    assert result["title"] == "Demo"
    from pathlib import Path

    assert not Path(calls[0][-1]).exists()  # Temporary audio removed after recognition.


@pytest.mark.asyncio
async def test_ambiguous_browser_never_records(monkeypatch):
    monkeypatch.setattr("singlayer.worker.shutil.which", lambda name: f"/usr/bin/{name}")

    async def missing(title):
        return None

    async def forbidden(*args):
        pytest.fail("Must not capture ambiguous audio")

    monkeypatch.setattr("singlayer.worker.audio_target", missing)
    monkeypatch.setattr("singlayer.worker.browser_sample", forbidden)
    assert (await recognize())["missing"]


@pytest.mark.asyncio
async def test_broken_native_recognizer_never_captures(monkeypatch):
    monkeypatch.setattr("singlayer.worker.shutil.which", lambda name: None)
    monkeypatch.setattr("singlayer.worker.importlib.util.find_spec", lambda name: object())

    async def crash(*args, **kwargs):
        raise RuntimeError("Proceso falló (-11)")

    async def forbidden(*args):
        pytest.fail("Broken engine must be rejected before capture")

    monkeypatch.setattr("singlayer.worker.command", crash)
    monkeypatch.setattr("singlayer.worker.audio_target", forbidden)
    result = await recognize()
    assert result["missing"]
    assert "ShazamIO" in result["error"]
