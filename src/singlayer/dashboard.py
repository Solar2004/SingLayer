"""Native monochrome player panel. Backend events, never fabricated progress."""

import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

from PyQt6.QtCore import (
    QBuffer,
    QByteArray,
    QIODevice,
    QLockFile,
    QProcess,
    QProcessEnvironment,
    QSettings,
    QStandardPaths,
    Qt,
    QTimer,
    QUrl,
)
from PyQt6.QtGui import QColor, QDesktopServices, QIcon, QImageReader, QPixmap
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .audio_meter import AudioMeter
from .overlay_link import OverlayLink, adjusted_document, managed_environment, snapshot

ROOT = Path(__file__).resolve().parents[2]
ICONS = {
    "Chromium": "chromium",
    "Brave": "brave-browser",
    "Chrome": "google-chrome",
    "Firefox": "firefox",
    "Vivaldi": "vivaldi",
    "Edge": "microsoft-edge",
}
STATES = {
    "running": "◌",
    "done": "●",
    "empty": "○",
    "missing": "!",
    "error": "!",
    "warning": "!",
    "skipped": "–",
}


def label(text="", name=""):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setWordWrap(True)
    widget.setObjectName(name)
    return widget


def terminate(process, timeout=2800):
    if process.state() != QProcess.ProcessState.NotRunning:
        process.terminate()
        if not process.waitForFinished(timeout):
            process.kill()
            process.waitForFinished(1000)


class TitleBar(QWidget):
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.window().windowHandle():
            self.window().windowHandle().startSystemMove()

    def mouseDoubleClickEvent(self, event):
        self.window().showNormal() if self.window().isMaximized() else self.window().showMaximized()


class Dashboard(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SingLayer")
        self.setWindowIcon(QIcon.fromTheme("audio-headphones"))
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(860, 620)
        self.setMinimumSize(780, 580)
        self.settings = QSettings("SingLayer", "Panel")
        self.track = self.document = self.job = self.cover_reply = self.blur = None
        self.plain = self.bridge_error = ""
        self.wanted = self.online = self.pending = self.overlay_attempted = False
        self.cover_revision = None
        self.job_epoch = 0
        self.events = {}
        self.retiring_jobs = set()
        self.result_cache = {}
        self._source_document = None
        self._adjustment = None
        self._adjusted_document = None
        self.network = QNetworkAccessManager(self)
        self.bridge, self.overlay, self.installer = QProcess(self), QProcess(self), QProcess(self)
        self.link = OverlayLink(self)
        self.build_ui()
        self.link.connected.connect(
            lambda active: self.overlay_button.setToolTip(
                "Overlay conectado" if active else "Overlay desconectado"
            )
        )
        for process, name in ((self.bridge, "Conector"), (self.overlay, "Overlay")):
            process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
            process.readyReadStandardOutput.connect(lambda p=process, n=name: self.process_logs(p, n))
            process.errorOccurred.connect(lambda _, n=name: self.activity.setText(f"No se pudo iniciar: {n}"))
        self.installer.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.installer.readyReadStandardOutput.connect(
            lambda: self.engine_button.setToolTip(
                bytes(self.installer.readAllStandardOutput()).decode(errors="replace")[-1600:]
            )
        )
        self.installer.finished.connect(self.install_finished)
        self.installer.errorOccurred.connect(lambda _: self.install_finished(-1))
        self.overlay.finished.connect(self.overlay_finished)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(700)
        self.check_engines()
        self.poll()

    def button(self, text, callback, layout, tooltip=None):
        button = QPushButton(text)
        button.clicked.connect(callback)
        if tooltip:
            button.setToolTip(tooltip)
            button.setAccessibleName(tooltip)
        layout.addWidget(button)
        return button

    def build_ui(self):
        self.setStyleSheet("""
            QWidget { color: #eeeeee; font: 13px 'Noto Sans'; }
            QWidget#surface { background: rgba(24,24,26,242); border: 1px solid #494949; border-radius: 20px; }
            QLabel { background: transparent; border: none; }
            QLabel#brand { font: 17px 'Noto Sans'; letter-spacing: 3px; }
            QLabel#title { font: 25px 'Noto Sans'; font-weight: 600; }
            QLabel#muted { color: #aaaaaa; font-size: 12px; }
            QLabel#cover { background: #28282a; border: 1px solid #555555; border-radius: 16px; font: 58px 'Noto Sans'; }
            QPushButton, QToolButton, QComboBox { background: #353537; border: 1px solid #555555; border-radius: 9px; padding: 10px; }
            QPushButton:hover, QToolButton:hover { background: #4b4b4e; }
            QPushButton:checked { background: #eeeeee; color: #181818; }
            QPushButton:disabled { color: #777777; }
            QPushButton:focus, QLineEdit:focus, QDoubleSpinBox:focus { border: 1px solid #ffffff; }
            QListWidget, QPlainTextEdit { background: #202022; border: 1px solid #3c3c3e; border-radius: 10px; padding: 6px; }
            QListWidget::item { padding: 5px; }
            QLineEdit, QDoubleSpinBox { background: #303032; border: 1px solid #555555; border-radius: 5px; padding: 6px; }
            QProgressBar { background: #414143; border: none; border-radius: 2px; max-height: 4px; }
            QProgressBar::chunk { background: #dddddd; border-radius: 2px; }
            QDialog, QMessageBox { background: #242426; }
            QCheckBox { padding: 5px 0; }
            QComboBox QAbstractItemView { background: #303032; color: #eeeeee; }
        """)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        surface = QWidget()
        surface.setObjectName("surface")
        outer.addWidget(surface)
        layout = QVBoxLayout(surface)
        layout.setContentsMargins(24, 18, 24, 24)
        header = TitleBar()
        head = QHBoxLayout(header)
        head.setContentsMargins(0, 0, 0, 10)
        brand = label("SINGLAYER", "brand")
        brand.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        head.addWidget(brand)
        head.addStretch()
        self.browser = QComboBox()
        self.browser.addItem(QIcon.fromTheme("web-browser"), "Auto")
        for name, icon in ICONS.items():
            self.browser.addItem(QIcon.fromTheme(icon), name)
        self.browser.setCurrentText(self.settings.value("browser-label", "Auto"))
        self.browser.setToolTip(
            "Chromium no distingue Brave/Chrome/Vivaldi. Selecciona el icono del navegador que usas."
        )
        self.browser.currentTextChanged.connect(lambda name: self.settings.setValue("browser-label", name))
        head.addWidget(self.browser)
        for text, tooltip, callback in (
            ("−", "Minimizar", self.showMinimized),
            ("×", "Cerrar y detener", self.close),
        ):
            button = QToolButton()
            button.setText(text)
            button.setToolTip(tooltip)
            button.setAccessibleName(tooltip)
            button.clicked.connect(callback)
            head.addWidget(button)
        layout.addWidget(header)
        body = QHBoxLayout()
        body.setSpacing(28)
        left = QVBoxLayout()
        self.cover = label("♫", "cover")
        self.cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover.setFixedSize(252, 252)
        glow = QGraphicsDropShadowEffect(self.cover)
        glow.setBlurRadius(28)
        glow.setOffset(0, 0)
        glow.setColor(QColor(255, 255, 255, 35))
        self.cover.setGraphicsEffect(glow)
        left.addWidget(self.cover)
        self.source_label = label("SIN REPRODUCCIÓN", "muted")
        left.addWidget(self.source_label)
        self.meter = AudioMeter()
        self.meter.failure.connect(lambda text: self.audio_note.setText(text))
        left.addWidget(self.meter)
        self.audio = QCheckBox("Audio del sistema")
        self.audio.setToolTip(
            "Permite espectro local y reconocimiento en paralelo mediante huellas de hasta 3 fragmentos enviadas a Shazam. Captura cualquier sonido que salga por los altavoces. No usa micrófono ni guarda audio."
        )
        self.audio.toggled.connect(self.audio_changed)
        left.addWidget(self.audio)
        self.audio_note = label("Espectro apagado · Shazam sin permiso", "muted")
        left.addWidget(self.audio_note)
        left.addStretch()
        body.addLayout(left)
        right = QVBoxLayout()
        right.setSpacing(12)
        self.connection = label("○ Sin conexión", "muted")
        self.title = label("Tu próxima canción", "title")
        self.artist = label("Abre SoundCloud, Spotify o YouTube", "muted")
        for widget in (self.connection, self.title, self.artist):
            right.addWidget(widget)
        self.timeline = QProgressBar()
        self.timeline.setRange(0, 1000)
        self.timeline.setValue(0)
        self.timeline.setTextVisible(False)
        right.addWidget(self.timeline)
        self.clock = label("— : —", "muted")
        right.addWidget(self.clock)
        controls = QHBoxLayout()
        self.button("Conectar", self.start, controls)
        self.overlay_button = self.button("Letras", lambda: None, controls)
        self.overlay_button.setCheckable(True)
        self.overlay_button.setChecked(True)
        self.overlay_button.toggled.connect(self.toggle_overlay)
        self.button("Shazam", lambda: self.search(True), controls)
        self.button("■", self.stop, controls, "Detener")
        right.addLayout(controls)
        self.activity = label("Lista para conectar", "muted")
        right.addWidget(self.activity)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        right.addWidget(self.progress)
        self.steps = QListWidget()
        self.steps.setMinimumHeight(110)
        self.steps.setAccessibleName("Intentos de búsqueda y reconocimiento")
        right.addWidget(self.steps, 1)
        actions = QHBoxLayout()
        self.button("Buscar", self.manual_search, actions)
        self.button("Sincronizar", self.show_lines, actions)
        self.extension_button = self.button(
            "Extensión ↗",
            lambda: QDesktopServices.openUrl(
                QUrl(
                    "https://chromewebstore.google.com/detail/webnowplaying/jfakgfcdgpghbbefmdfjkbdlibjgnbli"
                )
            ),
            actions,
            "Instalar o configurar WebNowPlaying. Sin conexión no significa necesariamente que no esté instalada.",
        )
        right.addLayout(actions)
        self.engine_button = self.button(
            "Instalar motores",
            self.install_engines,
            right,
            "Instalar ShazamIO, syncedlyrics y NumPy desde PyPI en el entorno de SingLayer",
        )
        body.addLayout(right, 1)
        layout.addLayout(body, 1)
        self.offset, self.speed = QDoubleSpinBox(), QDoubleSpinBox()
        self.offset.setRange(-3600, 3600)
        self.offset.setSingleStep(0.25)
        self.offset.setSuffix(" s")
        self.offset.setToolTip("Adelanta (+) o retrasa (−) las letras. No cambia la música.")
        self.speed.setRange(0.5, 2)
        self.speed.setDecimals(3)
        self.speed.setSingleStep(0.01)
        self.speed.setValue(1)
        self.speed.setSuffix(" ×")
        self.speed.setToolTip(
            "Velocidad de las letras; para slowed suele ser menor que 1. No altera el audio."
        )
        footer = QHBoxLayout()
        footer.addWidget(label("AJUSTE DE LETRA", "muted"))
        footer.addStretch()
        for name, spin in (("Desfase", self.offset), ("Velocidad", self.speed)):
            footer.addWidget(label(name, "muted"))
            footer.addWidget(spin)
            spin.valueChanged.connect(self.publish)
        layout.addLayout(footer)

    def poll(self):
        if self.pending:
            return
        self.pending = True
        request = QNetworkRequest(QUrl("http://127.0.0.1:8975/status"))
        request.setTransferTimeout(1800)
        reply = self.network.get(request)
        reply.finished.connect(lambda: self.receive(reply))

    def receive(self, reply):
        self.pending = False
        try:
            data = json.loads(bytes(reply.readAll()))
            if data.get("service") != "singlayer" or data.get("api_version") != 2:
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            self.online = False
            self.connection.setText("○ Conector apagado o antiguo")
            if self.track:
                self.cancel_job()
                self.track = self.document = None
                self.publish()
                self.title.setText("Sin conexión")
                self.cover.clear()
                self.cover.setText("♫")
            self.activity.setText(
                self.bridge_error or "Pulsa Conectar; cierra antes cualquier versión anterior."
            )
            return
        finally:
            reply.deleteLater()
        self.online = True
        count, families = data.get("browsers", 0), data.get("browser_families", [])
        self.connection.setText(
            "● " + (" · ".join(families) or "Navegador") if count else "○ Esperando extensión · puerto 8975"
        )
        self.browser.setEnabled(bool(count))
        if self.browser.currentText() == "Auto" and families:
            self.browser.setItemIcon(0, QIcon.fromTheme(ICONS.get(families[0], "web-browser")))
        self.extension_button.setVisible(not count)
        track = data.get("track")
        identity, previous = track.get("id") if track else None, self.track.get("id") if self.track else None
        if identity != previous:
            self.cancel_job()
            self.document, self.plain, self.cover_revision = None, "", None
            self.cover.clear()
            self.cover.setText("♫")
            self.events.clear()
            self.steps.clear()
            for spin, value in ((self.offset, 0), (self.speed, 1)):
                spin.blockSignals(True)
                spin.setValue(value)
                spin.blockSignals(False)
        self.track = track
        if not track:
            self.title.setText("Esperando música")
            self.artist.setText("Recarga la pestaña tras instalar la extensión")
            self.clock.setText("— : —")
            self.timeline.setValue(0)
            self.publish()
            return
        self.title.setText(track["title"])
        self.artist.setText(track.get("artist", ""))
        self.source_label.setText(track.get("source", "NAVEGADOR").upper())
        position, duration = int(track.get("position", 0)), int(track.get("duration", 0))
        self.clock.setText(
            f"{position // 60}:{position % 60:02d} / {duration // 60}:{duration % 60:02d}"
            + (" · reloj detenido" if track.get("stale") else " · pausa" if not track.get("playing") else "")
        )
        self.timeline.setValue(int(1000 * min(position / duration, 1)) if duration else 0)
        revision = track.get("cover")
        if revision and revision != self.cover_revision:
            self.fetch_cover(revision, identity)
        if self.job and self.audio.isChecked() and (not track.get("playing") or track.get("stale")):
            self.cancel_job()
            self.activity.setText("Audio en pausa · pulsa Buscar para reintentar")
        if self.wanted and identity != previous:
            self.search()
        self.publish()

    def fetch_cover(self, revision, identity):
        self.cover_revision = revision
        if self.cover_reply:
            self.cover_reply.abort()
        request = QNetworkRequest(QUrl(f"http://127.0.0.1:8975/cover?rev={revision}"))
        request.setTransferTimeout(3000)
        reply = self.network.get(request)
        self.cover_reply = reply

        def done():
            raw = bytes(reply.readAll())
            if (
                self.track
                and self.track["id"] == identity
                and self.cover_revision == revision
                and len(raw) <= 1_500_000
            ):
                buffer = QBuffer()
                buffer.setData(QByteArray(raw))
                buffer.open(QIODevice.OpenModeFlag.ReadOnly)
                reader = QImageReader(buffer)
                size = reader.size()
                if 0 < size.width() <= 4096 and 0 < size.height() <= 4096:
                    pixmap = QPixmap.fromImage(reader.read())
                    if not pixmap.isNull():
                        self.cover.setPixmap(
                            pixmap.scaled(
                                250,
                                250,
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation,
                            )
                        )
            if self.cover_reply is reply:
                self.cover_reply = None
            reply.deleteLater()

        reply.finished.connect(done)

    def start(self):
        self.wanted = True
        self.bridge_error = ""
        if not self.online and self.bridge.state() == QProcess.ProcessState.NotRunning:
            self.bridge.start(sys.executable, ["-m", "singlayer", "bridge"])
        self.ensure_overlay()
        if self.track:
            self.search()
        self.poll()

    def ensure_overlay(self):
        if not self.wanted or not self.overlay_button.isChecked() or self.overlay_attempted:
            return
        self.overlay_attempted = True
        try:
            env = QProcessEnvironment()
            for key, value in managed_environment().items():
                env.insert(key, value)
            self.overlay.setProcessEnvironment(env)
            self.overlay.start(str(Path(sys.executable).parent / "kotonoha"), ["--port", "28746"])
            self.link.enabled = True
        except OSError as error:
            self.activity.setText(f"Overlay: {error}")

    def toggle_overlay(self, checked):
        if checked:
            self.overlay_attempted = False
            self.ensure_overlay()
        else:
            self.link.stop()
            terminate(self.overlay)
            self.overlay_attempted = False

    def publish(self, *_):
        adjustment = self.offset.value(), self.speed.value()
        if self._source_document is not self.document or self._adjustment != adjustment:
            self._source_document = self.document
            self._adjustment = adjustment
            self._adjusted_document = adjusted_document(self.document, *adjustment)
        self.link.update(self.track, self._adjusted_document)

    def search(self, recognize=False, override=None):
        if not self.track:
            self.activity.setText("Primero conecta una canción")
            return
        if recognize and (
            not self.audio.isChecked() or not self.track.get("playing") or self.track.get("stale")
        ):
            self.activity.setText("Activa Audio del sistema y reproduce una canción")
            return
        if self.installer.state() != QProcess.ProcessState.NotRunning:
            return
        self.cancel_job()
        self.events.clear()
        self.steps.clear()
        cache_key = (self.track["title"], self.track.get("artist", ""), self.track.get("duration"))
        if not recognize and override is None and cache_key in self.result_cache:
            self.job_event({"finished": True, "result": self.result_cache[cache_key]})
            self.activity.setText("Letra recuperada de esta sesión")
            return
        self.document, self.plain = None, ""
        self.publish()
        self.progress.setRange(0, 0)
        self.activity.setText("Reconociendo audio…" if recognize else "Buscando letras…")
        process = QProcess(self)
        self.job = process
        epoch = self.job_epoch
        data = {
            "track": override or self.track,
            "recognize": recognize,
            "audio_allowed": bool(
                self.audio.isChecked() and self.track.get("playing") and not self.track.get("stale")
            ),
        }
        output = bytearray()

        def consume():
            output.extend(bytes(process.readAllStandardOutput()))
            if len(output) > 4_000_000:
                process.terminate()
                self.activity.setText("Respuesta del motor demasiado grande")
                return
            while b"\n" in output:
                line, _, rest = output.partition(b"\n")
                output[:] = rest
                if epoch != self.job_epoch:
                    continue
                try:
                    self.job_event(json.loads(line))
                except (ValueError, TypeError, KeyError):
                    self.document = None
                    self.activity.setText("Respuesta de motor no válida")

        process.readyReadStandardOutput.connect(consume)

        def finish(code, status):
            consume()
            if epoch == self.job_epoch:
                self.progress.setRange(0, 100)
                if code:
                    self.activity.setText("El motor terminó con un error")
                self.job = None
            self.retiring_jobs.discard(process)
            process.deleteLater()

        process.finished.connect(finish)

        def failed(error):
            if epoch == self.job_epoch:
                self.activity.setText("No se pudo iniciar el motor")
            if error == QProcess.ProcessError.FailedToStart:
                self.retiring_jobs.discard(process)
                if epoch == self.job_epoch:
                    self.job = None
                    self.progress.setRange(0, 100)
                process.deleteLater()

        process.errorOccurred.connect(failed)
        process.started.connect(
            lambda: (process.write(json.dumps(data).encode()), process.closeWriteChannel())
        )
        process.start(sys.executable, ["-m", "singlayer.worker", "resolve"])
        QTimer.singleShot(240_000, lambda: self.timeout_job(epoch))

    def timeout_job(self, epoch):
        if self.job and epoch == self.job_epoch:
            self.cancel_job()
            self.activity.setText("Tiempo máximo de búsqueda alcanzado")

    def job_event(self, event):
        if "fatal" in event:
            self.activity.setText(event["fatal"])
            return
        if event.get("finished"):
            result = event["result"]
            self.document, self.plain = result.get("document"), result.get("plain", "")
            if self.document:
                from kotonoha.lyrics.protocol import AdapterProtocolDecoder

                AdapterProtocolDecoder().decode(
                    json.loads(json.dumps(snapshot(self.track, self.document, 1))), observed_at=0
                )
            if self.track and (self.document or self.plain):
                key = (self.track["title"], self.track.get("artist", ""), self.track.get("duration"))
                if len(self.result_cache) >= 32 and key not in self.result_cache:
                    self.result_cache.pop(next(iter(self.result_cache)))
                self.result_cache[key] = result
            for value in self.events.values():
                if value["state"] == "running":
                    value.update(state="skipped", detail="Otro proveedor respondió")
            self.render_steps()
            self.activity.setText(
                f"Letra · {self.document['source']} · comprueba la sincronía"
                if self.document
                else "Texto sin tiempos · abre Sincronizar"
                if self.plain
                else "Sin coincidencia · prueba Buscar o Shazam"
            )
            self.progress.setRange(0, 100)
            self.progress.setValue(100 if self.document or self.plain else 0)
            self.publish()
            return
        self.events[event["stage"]] = event
        self.render_steps()
        if event["state"] == "running":
            self.activity.setText(event["detail"])

    def render_steps(self):
        self.steps.clear()
        for stage, event in self.events.items():
            self.steps.addItem(f"{STATES.get(event['state'], '○')}  {stage}  ·  {event['detail']}")
        self.steps.scrollToBottom()

    def cancel_job(self):
        self.job_epoch += 1
        process, self.job = self.job, None
        if process:
            self.retiring_jobs.add(process)
            process.terminate()

            # Do not block Qt while child workers release network/audio resources.
            def force_stop():
                if process in self.retiring_jobs:
                    process.kill()

            QTimer.singleShot(3800, force_stop)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

    def manual_search(self):
        if not self.track:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Buscar letras")
        form = QFormLayout(dialog)
        title, artist = QLineEdit(self.track["title"]), QLineEdit(self.track.get("artist", ""))
        form.addRow("Canción", title)
        form.addRow("Artista original", artist)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec() and title.text().strip():
            self.search(
                override={
                    **self.track,
                    "title": title.text().strip(),
                    "artist": artist.text().strip(),
                    "duration": None,
                    "manual": True,
                }
            )

    def show_lines(self):
        if not self.document and not self.plain:
            self.activity.setText("Aún no hay letras · prueba Buscar")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Estoy cantando aquí")
        dialog.resize(560, 450)
        layout = QVBoxLayout(dialog)
        if self.document:
            lines, identity = list(self.document["lines"]), self.track["id"]
            layout.addWidget(label("Doble clic en la línea que estás cantando para alinear."))
            listing = QListWidget()
            listing.addItems([line["text"] for line in lines])

            def align(item):
                if self.track and self.track["id"] == identity:
                    self.offset.setValue(
                        lines[listing.row(item)]["start"] - self.track["position"] * self.speed.value()
                    )
                    dialog.accept()

            listing.itemDoubleClicked.connect(align)
            layout.addWidget(listing)
        else:
            text = QPlainTextEdit(self.plain)
            text.setReadOnly(True)
            layout.addWidget(label("Texto sin tiempos: no se inventa sincronización."))
            layout.addWidget(text)
        dialog.exec()

    def audio_changed(self, enabled):
        if enabled:
            self.audio_note.setText("Salida del sistema · huellas a Shazam")
            self.meter.start()
        else:
            self.cancel_job()
            self.meter.stop()
            self.audio_note.setText("Espectro apagado · Shazam sin permiso")

    def check_engines(self):
        importlib.invalidate_caches()
        missing = [
            name for name in ("syncedlyrics", "shazamio", "numpy") if importlib.util.find_spec(name) is None
        ]
        self.engine_button.setVisible(bool(missing))
        self.engine_button.setEnabled(True)

    def install_engines(self):
        uv = shutil.which("uv")
        if not uv and (Path.home() / ".local/bin/uv").is_file():
            uv = str(Path.home() / ".local/bin/uv")
        if not uv:
            self.activity.setText("Falta uv · consulta la instalación del proyecto")
            return
        self.cancel_job()
        self.engine_button.setEnabled(False)
        self.activity.setText("Instalando motores desde PyPI…")
        self.installer.start(
            uv,
            [
                "pip",
                "install",
                "--cache-dir",
                str(ROOT / ".build" / "uv-cache"),
                "--python",
                sys.executable,
                "-r",
                str(ROOT / "requirements-engines.txt"),
            ],
        )

    def install_finished(self, code, *_):
        self.check_engines()
        self.activity.setText(
            "Motores instalados · pulsa Buscar" if code == 0 else "Error de instalación · revisa la conexión"
        )

    def process_logs(self, process, name):
        message = bytes(process.readAllStandardOutput()).decode(errors="replace")
        if (
            "Error" in message
            or "not permitted" in message
            or "Address already in use" in message
            or "already running" in message
        ):
            self.bridge_error = f"{name}: {message[-240:]}"
            self.activity.setText(self.bridge_error)

    def overlay_finished(self, code, status):
        self.link.stop()
        if self.wanted and self.overlay_button.isChecked():
            self.activity.setText(
                "Overlay cerrado: cierra cualquier Kotonoha anterior y vuelve a activar Letras"
            )

    def stop(self):
        self.wanted = False
        self.cancel_job()
        self.link.stop()
        self.audio.setChecked(False)
        self.meter.stop()
        terminate(self.overlay)
        terminate(self.bridge)
        self.overlay_attempted = False
        self.activity.setText("Detenido")

    def showEvent(self, event):
        super().showEvent(event)
        if QApplication.platformName().startswith("wayland"):
            try:
                import kotonoha
                from kotonoha.platform.native import LayerShellController
                from PyQt6 import sip

                if self.blur is None:
                    self.blur = LayerShellController(
                        str(Path(kotonoha.__file__).parent),
                        QApplication.platformName(),
                        os.environ.get("XDG_CURRENT_DESKTOP", ""),
                    )
                if self.blur.blur_available:
                    self.blur.set_blur_region(
                        sip.unwrapinstance(self.windowHandle()), 0, 0, self.width(), self.height(), 20
                    )
            except (ImportError, OSError, RuntimeError):
                pass

    def closeEvent(self, event):
        self.timer.stop()
        self.stop()
        for process in list(self.retiring_jobs):
            if process in self.retiring_jobs:
                terminate(process, 3800)
        terminate(self.installer)
        if self.blur and self.windowHandle():
            from PyQt6 import sip

            self.blur.clear_blur(sip.unwrapinstance(self.windowHandle()))
        event.accept()


def run():
    app = QApplication(sys.argv)
    lock = QLockFile(
        str(
            Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.RuntimeLocation))
            / "singlayer-panel.lock"
        )
    )
    if not lock.tryLock(0):
        QMessageBox.information(
            None, "SingLayer", "SingLayer ya está abierto. Busca su ventana en la barra de tareas."
        )
        return 0
    window = Dashboard()
    window.show()
    return app.exec()
