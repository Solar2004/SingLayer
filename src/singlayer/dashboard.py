"""Small native supervisor; never claims a lyric match from a browser connection."""

import json
import sys
from pathlib import Path

from PyQt6.QtCore import QProcess, QProcessEnvironment, Qt, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget

from .cli import overlay_environment


class Dashboard(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SingLayer")
        self.resize(540, 480)
        self.setStyleSheet("""
            QWidget { background: #192332; color: #edf3fa; font: 14px 'Noto Sans'; }
            QLabel { padding: 6px; }
            QLabel#track { font: 24px 'Noto Sans'; color: #8bdfff; }
            QPushButton { background: #304459; padding: 12px; border-radius: 8px; }
            QPushButton:focus { border: 2px solid #8bdfff; }
            QPushButton:hover { background: #40576f; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        self.connection = QLabel("Comprobando el conector…")
        self.track = QLabel("Esperando música")
        self.track.setObjectName("track")
        self.clock = QLabel("—")
        self.lyrics = QLabel("Letras: aún no comprobadas")
        self.notice = QLabel(
            "Shazam automático: no conectado.\nLos remixes pueden necesitar otras letras o ajustes de tiempo."
        )
        for label in (self.connection, self.track, self.clock, self.lyrics, self.notice):
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            layout.addWidget(label)
        self.start_button = QPushButton("Conectar y abrir letras")
        self.start_button.clicked.connect(self.start)
        layout.addWidget(self.start_button)
        settings = QPushButton("Instalar WebNowPlaying")
        settings.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl(
                    "https://chromewebstore.google.com/detail/webnowplaying/jfakgfcdgpghbbefmdfjkbdlibjgnbli"
                )
            )
        )
        layout.addWidget(settings)
        stop = QPushButton("Detener lo iniciado por esta ventana")
        stop.clicked.connect(self.stop)
        layout.addWidget(stop)
        self.network = QNetworkAccessManager(self)
        self.bridge = QProcess(self)
        self.overlay = QProcess(self)
        self.overlay.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.overlay.readyReadStandardOutput.connect(self.logs)
        self.bridge.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.bridge.readyReadStandardOutput.connect(self.bridge_logs)
        self.bridge.errorOccurred.connect(lambda _: self.connection.setText("No se pudo iniciar el conector"))
        self.overlay.errorOccurred.connect(lambda _: self.lyrics.setText("No se pudo iniciar Kotonoha"))
        self.buffer = ""
        self.wanted = False
        self.online = False
        self.pending = False
        self.last_track = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(1000)
        self.poll()

    def poll(self):
        if self.pending:
            return
        self.pending = True
        request = QNetworkRequest(QUrl("http://127.0.0.1:8975/status"))
        request.setTransferTimeout(1500)
        reply = self.network.get(request)
        reply.finished.connect(lambda: self.receive(reply))

    def receive(self, reply):
        self.pending = False
        try:
            data = json.loads(bytes(reply.readAll()))
            if data.get("service") != "singlayer":
                raise ValueError()
        except (ValueError, TypeError):
            self.online = False
            self.connection.setText(
                "Conector no disponible o versión antigua. Cierra el antiguo proceso y pulsa Conectar."
            )
            self.track.setText("Sin datos actuales")
            self.clock.setText("—")
            self.overlay.terminate()
            self.lyrics.setText("Letras: sin conexión comprobada")
            return
        finally:
            reply.deleteLater()
        self.online = True
        self.connection.setText(f"Navegadores conectados: {data['browsers']}")
        track = data.get("track")
        if not track:
            self.track.setText("Esperando una canción de WebNowPlaying")
            self.clock.setText("Configura el adaptador en el puerto 8975.")
            self.overlay.terminate()
            self.lyrics.setText("Letras: esperando canción")
            self.last_track = None
            return
        identity = (track["title"], track["artist"])
        if identity != self.last_track:
            self.last_track = identity
            self.lyrics.setText("Letras: esperando resultado del overlay")
        self.track.setText(f"{identity[0]}\n{identity[1]}")
        position = int(track["position"])
        self.clock.setText(
            f"{position // 60}:{position % 60:02d} · "
            + (
                "Reloj sin actualizar"
                if track["stale"]
                else "Reproduciendo"
                if track["playing"]
                else "En pausa"
            )
        )
        if self.wanted and self.overlay.state() == QProcess.ProcessState.NotRunning:
            self.wanted = False  # No automatic crash/restart loop.
            try:
                env = overlay_environment()
                qt_env = QProcessEnvironment()
                for key, value in env.items():
                    qt_env.insert(key, value)
                self.overlay.setProcessEnvironment(qt_env)
                self.overlay.start(str(Path(sys.executable).parent / "kotonoha"), [])
            except OSError as error:
                self.lyrics.setText(f"No se pudo preparar el overlay: {error}")

    def start(self):
        self.wanted = True
        if not self.online and self.bridge.state() == QProcess.ProcessState.NotRunning:
            self.bridge.start(sys.executable, ["-m", "singlayer", "bridge"])
        self.poll()

    def logs(self):
        self.buffer += bytes(self.overlay.readAllStandardOutput()).decode(errors="replace")
        lines = self.buffer.split("\n")
        self.buffer = lines.pop()[-8192:]
        for line in lines:
            if "lyrics resolution started" in line:
                self.lyrics.setText("Letras: buscando…")
            elif "LYRICS DISPLAY ACTIVE" in line:
                self.lyrics.setText(
                    "Letras encontradas. La coincidencia temporal aún debes comprobarla al cantar."
                )
            elif "reason=no-source-result" in line:
                self.lyrics.setText(
                    "No se encontraron letras. Usa la lupa del overlay para buscar título y artista originales."
                )

    def bridge_logs(self):
        text = bytes(self.bridge.readAllStandardOutput()).decode(errors="replace")
        if "Error" in text or "not permitted" in text:
            self.connection.setText("Error del conector: " + text[-500:])

    def stop(self):
        self.wanted = False
        self.overlay.terminate()
        self.bridge.terminate()

    def closeEvent(self, event):
        self.stop()
        for process in (self.overlay, self.bridge):
            if not process.waitForFinished(2000) and process.state() != QProcess.ProcessState.NotRunning:
                process.kill()
                process.waitForFinished(1000)
        event.accept()


def run():
    app = QApplication(sys.argv)
    window = Dashboard()
    window.show()
    return app.exec()
