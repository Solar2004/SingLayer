"""Use Kotonoha's existing adapter protocol, with one isolated managed profile."""

import copy
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

from PyQt6.QtCore import QObject, QTimer, QUrl, pyqtSignal
from PyQt6.QtNetwork import QAbstractSocket
from PyQt6.QtWebSockets import QWebSocket


def adjusted_document(document, offset=0.0, speed=1.0, duration=None):
    if not math.isfinite(offset) or not math.isfinite(speed) or not 0.25 <= speed <= 2:
        raise ValueError("Ajuste temporal inválido")
    result = copy.deepcopy(document)
    if result:
        for line in result["lines"]:
            for span in [line, *line.get("words", [])]:
                for key in ("start", "end"):
                    if span.get(key) is not None:
                        span[key] = max(0, (span[key] - offset) / speed)
        if duration is not None:
            if not math.isfinite(duration) or duration <= 0:
                raise ValueError("Duración de canción inválida")
            cropped = []
            for line in result["lines"]:
                line["end"] = min(line["end"] if line.get("end") is not None else duration, duration)
                if line["start"] >= line["end"]:
                    continue
                line["words"] = [word for word in line.get("words", [])
                                 if word["start"] < line["end"] and word["end"] > line["start"]]
                for word in line["words"]:
                    word["start"] = max(word["start"], line["start"])
                    word["end"] = min(word["end"], line["end"])
                cropped.append(line)
            result["lines"] = cropped
    return result


def snapshot(track, document, sequence):
    return {
        "protocol": "kotonoha.adapter",
        "version": 1,
        "type": "snapshot",
        "adapter": "singlayer",
        "sequence": sequence,
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "playback": {
            "playerId": "browser",
            "status": "Playing"
            if track and track.get("playing") and not track.get("stale")
            else "Paused"
            if track
            else "Stopped",
            "positionS": track.get("position", 0) if track else None,
            "durationS": track.get("duration") if track else None,
            "track": {
                "stableId": track["id"],
                "title": track["title"],
                "rawTitle": track["title"],
                "artist": track.get("artist", ""),
                "album": "",
            }
            if track
            else None,
        },
        "lyrics": document,
    }


def managed_environment():
    env = os.environ.copy()
    base = Path(env.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "singlayer" / "managed"
    target = base / "kotonoha" / "config.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_text(
            json.dumps(
                {
                    "display_sources": ["adapter"],
                    "panel_style": "text",
                    "opacity": 0,
                    "font_size": 34,
                    "context_font_size": 22,
                    "fx_glow": True,
                    "fx_word_pop": True,
                    "accent_start": "#e6e6e6",
                    "accent_end": "#ffffff",
                    "accent_sweep": "#ffffff",
                    "show_translation": True,
                    "translation_font_size": 22,
                    "ui_language": "en",
                    "anchor_top": False,
                    "margin_edge": 100,
                }
            ),
            encoding="utf-8",
        )
    # Upgrade only the managed profile's secondary-line slot. Existing font,
    # placement and other user choices remain untouched.
    config = json.loads(target.read_text(encoding="utf-8"))
    if not config.get("show_translation"):
        config["show_translation"] = True
        target.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    env["XDG_CONFIG_HOME"] = str(base)
    env["XDG_CACHE_HOME"] = str(
        Path(env.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "singlayer" / "managed"
    )
    return env


class OverlayLink(QObject):
    connected = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.socket = QWebSocket()
        self.socket.connected.connect(self.resend)
        self.socket.disconnected.connect(lambda: self.connected.emit(False))
        self.track = None
        self.document = None
        self.sequence = 0
        self.enabled = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.reconnect)
        self.timer.start(1500)

    def reconnect(self):
        if self.enabled and self.socket.state() == QAbstractSocket.SocketState.UnconnectedState:
            self.socket.open(QUrl("ws://127.0.0.1:28746/kotonoha/adapter"))

    def resend(self):
        self.connected.emit(True)
        self.sequence = 0
        self.update(self.track, self.document)

    def update(self, track, document):
        changed = (
            track is None
            or self.track is None
            or track.get("id") != self.track.get("id")
            or document != self.document
        )
        self.track, self.document = track, document
        if self.socket.state() != QAbstractSocket.SocketState.ConnectedState:
            return
        self.sequence += 1
        payload = snapshot(track, document, self.sequence)
        if not changed and self.sequence > 1 and track:
            payload = {
                "protocol": "kotonoha.adapter",
                "version": 1,
                "type": "clock",
                "adapter": "singlayer",
                "sequence": self.sequence,
                "capturedAt": payload["capturedAt"],
                "trackRef": f"singlayer:browser:{track['id']}",
                "positionS": track.get("position", 0),
                "status": payload["playback"]["status"],
            }
        self.socket.sendTextMessage(json.dumps(payload))

    def stop(self):
        self.enabled = False
        self.socket.close()
        self.track = self.document = None
