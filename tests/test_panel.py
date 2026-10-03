import json
import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")
pytest.importorskip("kotonoha")

from kotonoha.app.source_gate import SourceOwnershipCoordinator
from kotonoha.lyrics.lrc_parser import parse_lrc
from kotonoha.lyrics.protocol import AdapterProtocolDecoder
from kotonoha.receiver import AdapterReceiver
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from singlayer.audio_meter import spectrum
from singlayer.dashboard import Dashboard
from singlayer.overlay_link import adjusted_document, managed_environment, snapshot
from singlayer.worker import document

TRACK = {
    "id": "test-track",
    "title": "Original demo",
    "artist": "Singer",
    "position": 12,
    "duration": 180,
    "playing": True,
    "stale": False,
    "source": "SoundCloud",
}


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def panel(app, monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = Dashboard()
    window.timer.stop()
    yield window
    window.close()


def receive(panel, browsers=1, track=TRACK):
    data = {
        "service": "singlayer",
        "api_version": 2,
        "browsers": browsers,
        "browser_families": ["Chromium"] if browsers else [],
        "track": track,
    }
    panel.receive(SimpleNamespace(readAll=lambda: json.dumps(data).encode(), deleteLater=lambda: None))


def test_extension_visibility_and_real_status(panel):
    receive(panel, 0, None)
    assert not panel.extension_button.isHidden()
    receive(panel)
    assert panel.extension_button.isHidden()
    assert panel.title.text() == TRACK["title"]
    assert panel.title.textFormat() == Qt.TextFormat.PlainText
    assert panel.clock.text().startswith("0:12 / 3:00")
    assert not panel.audio.isChecked()


def test_worker_result_uses_real_kotonoha_parser_and_receiver(panel):
    receive(panel)
    doc = document(parse_lrc("[00:01.00]Original demo\n[00:04.00]Second line"), "test", "Demo", "Singer")
    panel.job_event({"finished": True, "result": {"document": doc}})
    assert panel.document["source"] == "test"
    published = []
    display = SimpleNamespace(publish=lambda *args: published.append(args), tick=lambda *args: None)
    receiver = AdapterReceiver(display, ownership=SourceOwnershipCoordinator(["adapter"]))
    assert receiver.ingest(json.dumps(snapshot(TRACK, doc, 1)), client_id=42)
    assert published[-1][1].source_id == "test"


def test_slowed_transform_and_word_timing_are_valid():
    doc = document(
        parse_lrc("[00:10.00]<00:10.00>Hello <00:11.00>world\n[00:12.00]Next"), "test", "Demo", "Singer"
    )
    shifted = adjusted_document(doc, offset=2, speed=0.8)
    assert shifted["lines"][0]["start"] == 10
    assert doc["lines"][0]["start"] == 10
    assert shifted["lines"][0]["words"][1]["start"] == 11.25
    AdapterProtocolDecoder().decode(json.loads(json.dumps(snapshot(TRACK, shifted, 1))), observed_at=0)
    with pytest.raises(ValueError):
        adjusted_document(doc, speed=0)


def test_managed_profile_does_not_follow_arbitrary_mpris(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    env = managed_environment()
    from pathlib import Path

    config = Path(env["XDG_CONFIG_HOME"]) / "kotonoha" / "config.json"
    assert json.loads(config.read_text())["display_sources"] == ["adapter"]


def test_real_fft_not_an_idle_animation():
    np = pytest.importorskip("numpy")
    silent = spectrum(bytes(8192))
    tone = (np.sin(2 * np.pi * 1000 * np.arange(4096) / 16000) * 16000).astype("<i2")
    active = spectrum(tone.tobytes())
    assert max(silent) == 0
    assert max(active) > 0.5
    assert min(active) < 0.1
