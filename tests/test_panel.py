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
    monkeypatch.setattr(Dashboard, "bootstrap", lambda self: None)
    window = Dashboard()
    window.timer.stop()
    window.audio_timer.stop()
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


def test_minimal_controls_and_automatic_start(panel, monkeypatch):
    from PyQt6.QtWidgets import QPushButton

    assert not hasattr(panel, "steps")
    assert not hasattr(panel, "engine_button")
    assert not hasattr(panel, "audio")
    assert not any(
        b.text() in {"Conectar", "Shazam", "Instalar motores"} for b in panel.findChildren(QPushButton)
    )
    calls = []
    panel.track = TRACK
    panel.online = True
    monkeypatch.setattr(panel, "ensure_overlay", lambda: calls.append("overlay"))
    monkeypatch.setattr(panel, "search", lambda: calls.append("search"))
    panel.start()
    assert panel.wanted
    assert calls == ["overlay", "search"]


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


def test_multiline_follows_clock_and_aligns_selected_line(panel):
    receive(panel)
    panel.document = document(
        parse_lrc("[00:01.00]First demo\n[00:04.00]Second demo\n[00:20.00]Third demo"),
        "test",
        "Demo",
        "Singer",
    )
    panel.publish()
    panel.toggle_lines(True)
    assert panel.lyric_preview.isHidden()
    assert panel.lyric_lines.count() == 3
    assert panel.lyric_lines.currentRow() == 1
    panel.align_visible_line(panel.lyric_lines.item(2))
    assert panel.offset.value() == 8
    assert panel.lyric_lines.currentRow() == 2


def test_search_failure_does_not_claim_catalog_absence_on_capture_error(panel):
    panel.events = {"shazam-1": {"state": "error", "detail": "No isolated stream"}}
    assert "audio no disponible" in panel.search_failure()
    assert "No isolated stream" in panel.activity.toolTip()


def test_two_anchor_calibration_updates_speed_without_changing_browser(panel):
    receive(panel, track={**TRACK, "position": 20})
    panel.document = document(
        parse_lrc("[00:19.00]First\n[01:07.00]Second\n[02:00.00]Third"), "test", "Demo", "Singer"
    )
    panel.publish()
    panel.begin_calibration()
    panel.align_visible_line(panel.lyric_lines.item(0))
    panel.track = {**panel.track, "position": 80}
    panel.align_visible_line(panel.lyric_lines.item(1))
    assert panel.speed.value() == pytest.approx(0.8)
    assert panel.offset.value() == pytest.approx(3)
    assert panel.track["position"] == 80
    assert not panel.calibrating
    panel.reset_alignment()
    assert panel.speed.value() == 1
    assert panel.offset.value() == 0


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


def test_seek_discards_live_epoch_and_old_document(panel, monkeypatch):
    receive(panel)
    panel.live_enabled = True
    panel.live_document = {"lines": []}
    epoch = panel.live_epoch
    monkeypatch.setattr(panel, "start_live", lambda: None)
    receive(panel, track={**TRACK, "position": 90})
    assert panel.live_epoch > epoch
    assert panel.live_document is None


def test_last_resort_enables_live_and_catalog_does_not(panel, monkeypatch):
    receive(panel)
    starts = []
    monkeypatch.setattr(panel, "start_live", lambda: starts.append(panel.live_enabled))
    panel.job_event({"finished": True, "result": {}})
    assert starts[-1] is True
    doc = document(parse_lrc("[00:01]Original demonstration line"), "test", "Demo", "Singer")
    panel.job_event({"finished": True, "result": {"document": doc}})
    assert starts[-1] is False


def test_sped_up_catalog_enables_acoustic_alignment(panel, monkeypatch):
    receive(panel, track={**TRACK, "title": "Singer - Demo (sped up)"})
    monkeypatch.setattr(panel, "start_live", lambda: None)
    doc = document(parse_lrc("[00:01]Original demonstration line"), "test", "Demo", "Singer")
    panel.job_event({"finished": True, "result": {"document": doc}})
    assert panel.live_enabled
