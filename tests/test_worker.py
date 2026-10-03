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

    async def capture(argv, **kwargs):
        calls.append(argv)
        if len(calls) == 1:
            return b"fixture-wav"
        return json.dumps({"track": {"title": "Demo", "subtitle": "Singer"}}).encode()

    monkeypatch.setattr("singlayer.worker.command", capture)
    result = await recognize()
    assert result["title"] == "Demo"
    assert "@DEFAULT_MONITOR@" in calls[0]
    assert calls[0][calls[0].index("-t") + 1] == "12"
    from pathlib import Path

    assert not Path(calls[1][-1]).exists()  # Temporary audio removed after recognition.
