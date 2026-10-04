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
    panel.lyric_source = "catalog"
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
    assert panel.lyric_lines.currentItem().text().endswith("Third demo")


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


def test_last_resort_enables_live_and_reliable_catalog_does_not(panel, monkeypatch):
    receive(panel, track={**TRACK, "source": "YouTube", "artist": "Singer"})
    starts = []
    monkeypatch.setattr(panel, "start_live", lambda: starts.append(panel.live_enabled))
    panel.job_event({"finished": True, "result": {}})
    assert starts[-1] is True
    doc = document(parse_lrc("[00:01]Original demonstration line"), "test", "Demo", "Singer")
    panel.job_event({"finished": True, "result": {"document": doc}})
    assert starts[-1] is True


def test_sped_up_catalog_enables_acoustic_alignment(panel, monkeypatch):
    receive(panel, track={**TRACK, "title": "Singer - Demo (sped up)"})
    monkeypatch.setattr(panel, "start_live", lambda: None)
    doc = document(parse_lrc("[00:01]Original demonstration line"), "test", "Demo", "Singer")
    panel.job_event({"finished": True, "result": {"document": doc}})
    assert panel.live_enabled


def test_browser_choice_restarts_capture_and_sets_worker_environment(panel, monkeypatch):
    calls = []
    panel.wanted = True
    panel.track = TRACK
    panel.audio_target = {"backend": "pipewire", "serial": 123}
    for name in ("cancel_job", "stop_live", "probe_audio", "search"):
        monkeypatch.setattr(panel, name, lambda name=name, **kwargs: calls.append(name))
    monkeypatch.setattr(panel.meter, "stop", lambda: calls.append("meter"))
    panel.browser.setCurrentText("Brave")
    assert panel.audio_environment().value("SINGLAYER_BROWSER") == "Brave"
    assert panel.settings.value("browser-label") == "Brave"
    assert panel.audio_target is None
    assert calls == ["cancel_job", "stop_live", "meter", "probe_audio", "search"]


def test_live_guide_uses_live_text_and_preserves_measured_timing(panel):
    panel.track = TRACK
    panel.live_document = {
        "source": "crisperwhisper-local", "title": "", "artist": "", "timing": "Word",
        "lines": [{"text": "Hello", "start": 12, "end": 14, "words": [], "translation": ""}],
    }
    panel.guide_cache[("Hello",)] = [{"phonetic": "jelou", "tip": ""}]
    panel.reading_mode.setCurrentIndex(2)
    assert panel.guide_key == ("Hello",)
    assert panel._adjusted_document["lines"][0]["translation"] == "jelou"
    assert panel._adjusted_document["lines"][0]["start"] == 12
    # A new fragment must never inherit the previous fragment's pronunciation.
    panel.live_document = {**panel.live_document, "lines": [{"text": "Goodbye", "start": 20, "end": 22, "words": [], "translation": ""}]}
    panel.publish()
    assert panel._adjusted_document["lines"][0]["translation"] == ""


def test_calibration_saved_for_exact_recording_and_catalog(panel, monkeypatch):
    monkeypatch.setattr(panel, "start_live", lambda: None)
    panel.track = TRACK
    doc = document(parse_lrc("[00:01]Original demo\n[00:05]Second line"), "test", "Demo", "Singer")
    panel.job_event({"finished": True, "result": {"document": doc}})
    panel.offset.setValue(3)
    panel.speed.setValue(.8)
    saved = panel.settings.value("alignments")
    # Simulate startup defaults without erasing the stored calibration.
    for spin, value in ((panel.offset, 0), (panel.speed, 1)):
        spin.blockSignals(True)
        spin.setValue(value)
        spin.blockSignals(False)
    panel.restore_alignment()
    assert (panel.offset.value(), panel.speed.value()) == (3, .8)
    panel.track = {**TRACK, "title": "Different upload"}
    panel.restore_alignment()
    assert (panel.offset.value(), panel.speed.value()) == (0, 1)
    assert panel.settings.value("alignments") == saved
    panel.track = TRACK
    panel.restore_alignment()
    panel.reset_alignment()
    panel.restore_alignment()
    assert (panel.offset.value(), panel.speed.value()) == (0, 1)


def test_seek_reuses_only_measured_fragments_of_same_recording(panel, monkeypatch):
    receive(panel)
    doc = {"source": "whisper-vulkan", "title": "", "artist": "", "timing": "Line",
           "lines": [{"text": "Measured phrase", "start": 2, "end": 5, "words": [], "translation": ""}]}
    panel.live_document = doc
    panel.remember_live()
    monkeypatch.setattr(panel, "start_live", lambda: None)
    receive(panel, track={**TRACK, "position": 2})
    assert panel.live_document is doc
    receive(panel, track={**TRACK, "id": "other-recording", "title": "Different upload"})
    assert panel.live_document is None


def test_automatic_clock_maps_future_catalog_and_shows_second_ranges(panel):
    panel.track = TRACK
    panel.document = document(parse_lrc("[00:19]First demo\n[00:43]Second demo\n[01:07]Third demo"), "test", "Demo", "Singer")
    panel.automatic_clock = {"offset": 3, "speed": .8, "anchors": 3}
    panel.publish()
    assert panel._adjusted_document["lines"][0]["start"] == 20
    assert panel._adjusted_document["lines"][1]["start"] == 50
    assert panel._adjusted_document["source"] == "audio-clock"
    assert panel.lyric_lines.item(0).text().startswith("00:20.00 – 00:50.00")
    panel.offset.setValue(2)
    assert panel.automatic_clock is None


def test_timeline_is_cropped_to_actual_song_duration_and_final_line_ends_there():
    doc = {"lines": [{"text": "in song", "start": 5, "end": 14, "words": []},
                     {"text": "outside song", "start": 20, "end": 25, "words": []}]}
    cropped = adjusted_document(doc, duration=12)
    assert len(cropped["lines"]) == 1
    assert cropped["lines"][0]["end"] == 12
    assert doc["lines"][0]["end"] == 14


def test_duration_crop_keeps_pronunciation_for_remaining_phrase(panel):
    panel.track = {**TRACK, "duration": 12}
    panel.document = document(parse_lrc("[00:05]Hello\n[00:20]Goodbye"), "test", "Demo", "Singer")
    panel.guide_cache[("Hello", "Goodbye")] = [
        {"phonetic": "jelou", "tip": ""}, {"phonetic": "gudbai", "tip": ""}]
    panel.reading_mode.setCurrentIndex(2)
    assert len(panel._adjusted_document["lines"]) == 1
    assert panel._adjusted_document["lines"][0]["translation"] == "jelou"
    assert panel._adjusted_document["lines"][0]["end"] == 12



@pytest.mark.parametrize("artist,source,duration", [("", "YouTube", 180), ("Uploader", "SoundCloud", 180),
                                                    ("Singer", "YouTube", 12)])
def test_uncertain_or_cropped_upload_starts_acoustic_alignment(panel, monkeypatch, artist, source, duration):
    panel.track = {**TRACK, "artist": artist, "source": source, "duration": duration}
    monkeypatch.setattr(panel, "start_live", lambda: None)
    doc = document(parse_lrc("[00:05]First original phrase\n[00:20]Later original phrase"), "test", "Demo", "Singer")
    panel.job_event({"finished": True, "result": {"document": doc}})
    assert panel.live_enabled



def test_delayed_audio_does_not_remove_full_catalog_after_search(panel, monkeypatch):
    panel.track = {**TRACK, "position": 42}
    monkeypatch.setattr(panel, "start_live", lambda: None)
    catalog = document(parse_lrc("[00:01]First original phrase\n[00:35]Current original phrase\n[01:00]Future original phrase"), "test", "Demo", "Singer")
    panel.job_event({"finished": True, "result": {"document": catalog}})
    panel.live_document = {"source": "audio-aligned", "lines": [
        {"text": "Past acoustic phrase", "start": 4, "end": 9, "words": [], "translation": ""}]}
    panel.publish()
    assert len(panel._adjusted_document["lines"]) == 3
    assert panel.lyric_preview.text() == ""
    assert panel._source_document is catalog
    assert panel.link.document is None  # Candidate lyrics must not overlay instrumental audio.
    assert panel.lyric_lines.count() == 3  # Still available for review/manual selection.
    # Seeking into a measured interval should still use its acoustic times.
    panel.track = {**panel.track, "position": 6}
    panel.publish()
    assert panel.lyric_preview.text() == "Past acoustic phrase"
    assert panel._source_document is panel.live_document
    panel.track = {**panel.track, "position": 42}
    panel.publish()
    assert panel.lyric_preview.text() == ""


def test_explicit_transcription_keeps_raw_words_even_with_catalog(panel, monkeypatch):
    monkeypatch.setattr(panel, "start_live", lambda: None)
    panel.track = TRACK
    panel.document = document(parse_lrc("[00:01]Catalog phrase"), "test", "Demo", "Singer")
    raw = {"source": "whisper-vulkan", "lines": [
        {"text": "Actual acoustic words", "start": 10, "end": 14, "words": [], "translation": ""}]}
    panel.observed_document = raw
    panel.lyric_source_picker.setCurrentIndex(panel.lyric_source_picker.findData("transcript"))
    assert panel.settings.value("lyric_source") == "transcript"
    assert panel._source_document is raw
    assert panel.lyric_preview.text() == "Actual acoustic words"
    panel.lyric_source_picker.setCurrentIndex(panel.lyric_source_picker.findData("catalog"))
    assert not panel.live_enabled
    assert panel._source_document is panel.document
    assert panel.lyric_preview.text() == "Catalog phrase"


def test_changing_engine_clears_acoustic_results_and_persists_choice(panel, monkeypatch):
    monkeypatch.setattr(panel, "start_live", lambda: None)
    panel.observed_document = {"lines": []}
    panel.live_cache["old"] = {"lines": []}
    panel.clock_anchors[1] = (2, 3)
    panel.automatic_clock = {"offset": 2, "speed": 1}
    panel.engine_picker.setCurrentIndex(panel.engine_picker.findData("crisper"))
    assert panel.engine_preference == "crisper"
    assert panel.settings.value("transcription_engine") == "crisper"
    assert panel.observed_document is None
    assert not panel.live_cache and not panel.clock_anchors
    assert panel.automatic_clock is None



def test_automatic_remix_uses_whisper_transcript_without_catalog_replacement(panel):
    panel.lyric_source = "auto"
    panel.track = {**TRACK, "title": "Demo Remix"}
    panel.document = document(parse_lrc("[00:01]Original catalog words"), "test", "Demo", "Singer")
    panel.engine_preference = "crisper"
    raw = {"source": "whisper-vulkan", "lines": [
        {"text": "Words actually sung in remix", "start": 10, "end": 14, "words": [], "translation": ""}]}
    panel.observed_document = raw
    panel.offset.blockSignals(True)
    panel.offset.setValue(9)
    panel.offset.blockSignals(False)
    panel.publish()
    assert panel.lyric_policy() == {"route": "transcript", "engine": "whisper"}
    assert panel._source_document is raw
    assert panel._adjusted_document["lines"][0]["start"] == 10
    assert panel.lyric_preview.text() == "Words actually sung in remix"
    assert panel.link.document["lines"][0]["text"] == "Words actually sung in remix"



def test_no_catalog_shows_crisper_words_with_original_acoustic_times(panel, monkeypatch):
    monkeypatch.setattr(panel, "start_live", lambda: None)
    panel.lyric_source = "auto"
    panel.engine_preference = "auto"
    panel.track = TRACK
    panel.job_event({"finished": True, "result": {"plain": "Untimed text cannot supply a clock"}})
    assert panel.lyric_policy() == {"route": "transcript", "engine": "crisper"}
    panel.observed_document = {"source": "crisperwhisper-local", "timing": "Word", "lines": [
        {"text": "Actual timed words", "start": 10, "end": 14, "translation": "", "words": [
            {"text": "Actual", "start": 10, "end": 11},
            {"text": " timed", "start": 11.5, "end": 12},
            {"text": " words", "start": 13, "end": 14}]}]}
    panel.publish()
    assert panel.lyric_preview.text() == "Actual timed words"
    assert panel.link.document["timing"] == "Word"
    assert panel.link.document["lines"][0]["words"][1]["start"] == 11.5



def test_unverified_catalog_does_not_claim_original_end_as_slowed_time(panel, monkeypatch):
    monkeypatch.setattr(panel, "start_live", lambda: None)
    panel.lyric_source = "auto"
    panel.track = {**TRACK, "title": "Song ULTRA SLOWED", "duration": 192, "position": 140}
    catalog = document(parse_lrc("[00:10]First phrase\n[02:14]Last original phrase"), "test", "Demo", "Singer")
    panel.job_event({"finished": True, "result": {"document": catalog}})
    assert panel.lyric_lines.item(1).text().startswith("Por sincronizar")
    assert "02:14" not in panel.lyric_lines.item(1).text()
    assert panel.lyric_lines.currentRow() == -1
    assert panel.link.document is None


def test_ultra_slowed_adjustment_can_reach_real_duration():
    doc = {"lines": [{"text": "Final phrase", "start": 70, "end": 78.8, "words": []}]}
    adjusted = adjusted_document(doc, offset=2, speed=.4, duration=192)
    assert adjusted["lines"][0]["end"] == pytest.approx(192)


def test_complete_audio_timing_is_available_for_future_and_seek(panel):
    panel.lyric_source = 'auto'
    panel.track = {**TRACK, 'duration': 192, 'position': 175}
    panel.full_completed = True
    panel.full_document = {'source': 'full-audio', 'lines': [
        {'text': 'Earlier measured words', 'start': 5, 'end': 9, 'words': [], 'translation': ''},
        {'text': 'Late words measured in full audio', 'start': 170, 'end': 180, 'words': [], 'translation': ''}]}
    panel.publish()
    assert panel.lyric_preview.text() == 'Late words measured in full audio'
    assert panel.link.document['lines'][1]['start'] == 170
    panel.track = {**panel.track, 'position': 6}
    panel.publish()
    assert panel.lyric_preview.text() == 'Earlier measured words'


def test_automatic_full_track_only_once_with_ready_exact_url(panel, monkeypatch):
    import time

    panel.lyric_source = 'auto'
    panel.track = {**TRACK, 'url': 'https://soundcloud.com/singer/song'}
    panel.wanted = True
    panel.track_seen_at = time.monotonic()-4
    calls = []
    monkeypatch.setattr(panel, 'analyze_full_track', calls.append)
    panel.maybe_full_track()
    panel.maybe_full_track()
    assert calls == [panel.track['url']]


def test_automatic_full_track_waits_for_playback_but_not_catalog_search(panel, monkeypatch):
    import time

    calls = []
    monkeypatch.setattr(panel, 'analyze_full_track', calls.append)
    panel.lyric_source = 'auto'
    panel.wanted = True
    panel.track_seen_at = time.monotonic()-4
    for patch in ({'url': None}, {'playing': False}, {'stale': True}):
        panel.track = {**TRACK, 'url': 'https://soundcloud.com/singer/song', **patch}
        panel.maybe_full_track()
    panel.track = {**TRACK, 'url': 'https://soundcloud.com/singer/song'}
    panel.track_seen_at = time.monotonic()
    panel.maybe_full_track()
    assert calls == []
    panel.track_seen_at = time.monotonic()-4
    panel.job = object()
    panel.maybe_full_track()
    panel.job = None
    assert calls == [panel.track["url"]]


def test_capture_progress_and_inference_wait_are_distinct(panel):
    panel.update_live_progress({'live_progress': 'capture', 'captured': 7, 'total': 24})
    assert panel.progress.maximum() == 24
    assert panel.progress.value() == 7
    assert '17 s' in panel.activity.text()
    panel.update_live_progress({'live_progress': 'transcribing', 'elapsed': 6.8})
    assert panel.progress.maximum() == 0
    assert '6 s de análisis' in panel.activity.text()
    assert 'faltan' not in panel.activity.text()


def test_delayed_transcript_explains_empty_current_lyrics(panel):
    panel.lyric_source = 'transcript'
    panel.track = {**TRACK, 'position': 40}
    panel.observed_document = {'source': 'audio-transcript', 'lines': [
        {'text': 'Past measured phrase', 'start': 5, 'end': 9, 'words': [], 'translation': ''}]}
    panel.publish()
    assert panel.lyric_preview.text() == ''
    assert '1 frase' in panel.transcription_hint.text()
    assert 'este segundo' in panel.transcription_hint.text()
    panel.track = {**panel.track, 'position': 6}
    panel.publish()
    assert panel.lyric_preview.text() == 'Past measured phrase'
    assert panel.transcription_hint.text() == ''


def test_partial_full_audio_is_visible_before_whole_track_finishes(panel):
    panel.lyric_source = 'auto'
    panel.track = {**TRACK, 'position': 50}
    panel.full_completed = False
    panel.full_document = {'source': 'full-audio', 'lines': [
        {'text': 'Measured current phrase', 'start': 48, 'end': 55, 'words': [], 'translation': ''}]}
    panel.full_original_document = panel.full_document
    panel.publish()
    assert panel.lyric_preview.text() == 'Measured current phrase'
    assert panel.link.document['source'] == 'full-audio'
    assert not panel.full_completed


@pytest.mark.parametrize('preference,expected', [('auto', 'auto'), ('crisper', 'crisper')])
def test_full_track_without_catalog_prefers_installed_gpu_unless_cpu_selected(panel, monkeypatch, preference, expected):
    from singlayer import transcriber_runtime

    called = []
    def select(value):
        called.append(value)
        raise ValueError('Stop before starting a worker')
    monkeypatch.setattr(transcriber_runtime, 'selected_engine', select)
    panel.track = TRACK
    panel.document = None
    panel.catalog_resolved = True
    panel.lyric_source = 'auto'
    panel.engine_preference = preference
    panel.analyze_full_track('https://soundcloud.com/singer/song')
    assert called == [expected]
