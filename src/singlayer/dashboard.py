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
    QAbstractItemView,
    QApplication,
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

from .alignment import calibrate
from .artwork import safe_cover_url
from .audio_meter import AudioMeter
from .diagnostics import log_path, record
from .overlay_link import OverlayLink, adjusted_document, managed_environment, snapshot
from .pronunciation import apply_guide

ROOT = Path(__file__).resolve().parents[2]
ICONS = {
    "Chromium": "chromium",
    "Brave": "brave-browser",
    "Chrome": "google-chrome",
    "Firefox": "firefox",
    "Vivaldi": "vivaldi",
    "Edge": "microsoft-edge",
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
        self.resize(820, 450)
        self.setMinimumSize(740, 420)
        self.settings = QSettings("SingLayer", "Panel")
        self.closing = False
        self.track = self.document = self.job = self.cover_reply = self.blur = None
        self.live_job = None
        self.live_epoch = 0
        self.live_enabled = False
        self.live_retry_at = 0
        self.clock_observed_at = None
        self.live_document = None
        self.catalog_candidates = []
        self.crisper = QProcess(self)
        self.crisper.setStandardOutputFile(QProcess.nullDevice())
        self.crisper.setStandardErrorFile(str(ROOT / ".build/crisper-server.log"))
        self.plain = self.bridge_error = ""
        self.wanted = self.online = self.pending = self.overlay_attempted = False
        self.cover_revision = None
        self.cover_attempts = {}
        self.job_epoch = 0
        self.events = {}
        self.retiring_jobs = set()
        self.result_cache = {}
        self.live_cache = {}
        self.observed_document = None
        self.clock_anchors = {}
        self.automatic_clock = None
        self.guide = None
        self.guide_cache = {}
        self.guide_key = None
        self.calibration_anchor = None
        self.calibrating = False
        self.ai_job = None
        self.ai_epoch = 0
        self._source_document = None
        self._adjustment = None
        self._adjusted_document = None
        self.network = QNetworkAccessManager(self)
        self.bridge, self.overlay, self.installer = QProcess(self), QProcess(self), QProcess(self)
        self.link = OverlayLink(self)
        self.audio_probe = QProcess(self)
        self.audio_target = None
        self.audio_probe.finished.connect(self.audio_probe_finished)
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
            lambda: self.activity.setToolTip(
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
        QTimer.singleShot(1000, self.bootstrap)
        self.audio_timer = QTimer(self)
        self.audio_timer.timeout.connect(self.probe_audio)
        self.audio_timer.start(3000)

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
            QToolButton { background: transparent; border: none; padding: 6px; }
            QToolButton:focus { border: 1px solid #aaaaaa; }
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
            "Navegador del que se captura audio. Auto rechaza varios flujos ambiguos; elige Brave, Chrome u otro para aislarlo."
        )
        self.browser.currentTextChanged.connect(self.browser_changed)
        self.browser.hide()
        self.browser_badge = QLabel()
        self.browser_badge.setFixedSize(22, 22)
        head.addWidget(self.browser_badge)
        more = QToolButton()
        more.setText("⋯")
        more.setToolTip("Ajustes y corrección manual")
        more.setAccessibleName("Ajustes y corrección manual")
        more.clicked.connect(self.show_settings)
        head.addWidget(more)
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
        self.meter.failure.connect(self.meter.setToolTip)
        left.addWidget(self.meter)
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
        self.overlay_button = QPushButton("Mostrar letras", self)
        self.overlay_button.setCheckable(True)
        self.overlay_button.setChecked(True)
        self.overlay_button.toggled.connect(self.toggle_overlay)
        self.overlay_button.hide()
        self.lyric_preview = label("", "title")
        right.addWidget(self.lyric_preview, 1)
        self.lyric_lines = QListWidget()
        self.lyric_lines.setAccessibleName("Letra completa; doble clic para alinear con la música")
        self.lyric_lines.setWordWrap(True)
        self.lyric_lines.setStyleSheet(
            "QListWidget { border: none; background: transparent; font-size: 16px; } QListWidget::item { padding: 8px; color: #aaaaaa; } QListWidget::item:selected { color: white; background: #353537; border-radius: 6px; }"
        )
        self.lyric_lines.itemDoubleClicked.connect(self.align_visible_line)
        self.lyric_lines.hide()
        self._visible_document = None
        right.addWidget(self.lyric_lines, 1)
        self.lines_button = QToolButton()
        self.lines_button.setText("≡")
        self.lines_button.setToolTip("Ver inicio y final de cada parte de la letra · doble clic para corregir")
        self.lines_button.setAccessibleName("Mostrar letra completa con desplazamiento automático")
        self.lines_button.setCheckable(True)
        self.lines_button.toggled.connect(self.toggle_lines)
        head.insertWidget(head.count() - 2, self.lines_button)
        self.activity = label("Lista para conectar", "muted")
        right.addWidget(self.activity)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        right.addWidget(self.progress)
        actions = QHBoxLayout()
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
            spin.valueChanged.connect(self.alignment_changed)
        self.adjustments = QWidget(self)
        self.adjustments.setLayout(footer)
        self.adjustments.hide()
        self.reading_mode = QComboBox(self)
        self.reading_mode.addItems(
            ["Original", "Pronunciación española · local", "Original + pronunciación · local"]
        )
        self.reading_mode.currentIndexChanged.connect(self.reading_changed)
        self.reading_mode.hide()

    def show_settings(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Ajustes")
        layout = QVBoxLayout(dialog)
        layout.addWidget(label("Corrección manual, solo si hace falta", "muted"))
        self.button("Buscar otra canción", self.manual_search, layout)
        self.button("Elegir otra versión de la letra", self.choose_version, layout)
        self.button("Alinear la letra", self.show_lines, layout)
        self.button(
            "Calibrar slowed / sped up con dos líneas",
            lambda: (dialog.accept(), self.begin_calibration()),
            layout,
        )
        self.button("Restablecer sincronización", self.reset_alignment, layout)
        self.button("Reintentar búsqueda", self.search, layout)
        layout.addWidget(self.overlay_button)
        layout.addWidget(self.adjustments)
        layout.addWidget(self.reading_mode)
        layout.addWidget(self.browser)
        self.browser.show()
        self.overlay_button.show()
        self.adjustments.show()
        self.reading_mode.show()
        self.button("Practicar pronunciación", self.practice, layout)
        self.button("Reintentar pronunciación", self.reading_changed, layout)
        self.button(
            "Abrir diagnóstico local",
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_path()))),
            layout,
        )
        layout.addWidget(
            label(
                "La pronunciación se calcula localmente. Es aproximada; conserva el idioma original y no traduce. No envía letras ni audio.",
                "muted",
            )
        )
        layout.addWidget(
            label(
                "Solo audio del navegador. Las huellas de reconocimiento se envían a Shazam; no se guarda la grabación.",
                "muted",
            )
        )
        dialog.exec()
        for widget in (self.overlay_button, self.adjustments, self.reading_mode, self.browser):
            widget.hide()
            widget.setParent(self)

    def cancel_ai(self):
        self.ai_epoch += 1
        process, self.ai_job = self.ai_job, None
        if process:
            process.terminate()
            self.retiring_jobs.add(process)
            QTimer.singleShot(3800, lambda: process.kill() if process in self.retiring_jobs else None)

    def reading_changed(self, *_):
        self.cancel_ai()
        self.progress.setRange(0, 100)
        self._adjustment = None
        self.publish()
        source = self.document if self.automatic_clock else (self.live_document or self.document)
        if not self.reading_mode.currentIndex() or not source:
            return
        key = tuple(line["text"] for line in source["lines"])
        if self.guide_key != key:
            self.guide = None
            self.guide_key = key
            self._adjustment = None
            self.publish()
        if key in self.guide_cache:
            self.guide = self.guide_cache[key]
            self._adjustment = None
            self.publish()
            return
        epoch = self.ai_epoch
        process = QProcess(self)
        self.ai_job = process
        self.activity.setText("Preparando pronunciación…")
        self.progress.setRange(0, 0)
        output = bytearray()

        def read():
            output.extend(bytes(process.readAllStandardOutput()))
            if len(output) > 200_000:
                process.kill()

        def finish(*_):
            read()
            self.retiring_jobs.discard(process)
            if epoch == self.ai_epoch:
                self.ai_job = None
                self.progress.setRange(0, 100)
                try:
                    result = json.loads(output)
                    if "fatal" in result:
                        raise ValueError(str(result["fatal"])[:240])
                    if len(result["guide"]) != len(key):
                        raise ValueError("Guía incompleta")
                    self.guide = result["guide"]
                    if len(self.guide_cache) >= 16:
                        self.guide_cache.pop(next(iter(self.guide_cache)))
                    self.guide_cache[key] = self.guide
                    self.activity.setText(f"Guía aproximada · {result['elapsed']:.2f} s")
                    self._adjustment = None
                    self.publish()
                except (ValueError, KeyError, TypeError) as error:
                    record("pronunciation_panel", type(error).__name__)
                    self.activity.setText("Pronunciación no disponible · pasa el cursor para ver el motivo")
                    self.activity.setToolTip(str(error)[:300] or "El proceso terminó sin respuesta")
            process.deleteLater()

        process.readyReadStandardOutput.connect(read)
        process.finished.connect(finish)
        process.errorOccurred.connect(
            lambda error: finish() if error == QProcess.ProcessError.FailedToStart else None
        )
        # Send text only. Never let the model alter timestamps or receive audio.
        payload = {"document": {"lines": [{"text": text} for text in key]}}
        process.started.connect(
            lambda: (process.write(json.dumps(payload).encode()), process.closeWriteChannel())
        )
        process.start(sys.executable, ["-m", "singlayer.worker", "pronunciation"])

        def deadline():
            if self.ai_job is process and epoch == self.ai_epoch:
                record("pronunciation_panel", "deadline_95s")
                process.kill()

        QTimer.singleShot(95_000, deadline)

    def practice(self):
        source = self.document if self.automatic_clock else (self.live_document or self.document)
        if not self.guide or not source:
            self.activity.setText("Activa la guía de pronunciación en ⋯")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Pronunciación · guía aproximada")
        dialog.resize(620, 420)
        layout = QVBoxLayout(dialog)
        text = QPlainTextEdit()
        text.setReadOnly(True)
        text.setPlainText(
            "\n\n".join(
                f"{line['text']}\n{item['phonetic']}" + (f"\n{item['tip']}" if item.get("tip") else "")
                for line, item in zip(source["lines"], self.guide)
            )
        )
        layout.addWidget(text)
        dialog.exec()

    def bootstrap(self):
        if self.closing:
            return
        self.start()
        if self.missing_engines:
            self.install_engines()

    def audio_environment(self):
        env = QProcessEnvironment.systemEnvironment()
        env.insert("SINGLAYER_BROWSER", self.browser.currentText())
        return env

    def browser_changed(self, name):
        self.settings.setValue("browser-label", name)
        self.browser_badge.setPixmap(self.browser.itemIcon(self.browser.currentIndex()).pixmap(20, 20))
        self.cancel_job()
        self.stop_live()
        terminate(self.audio_probe)
        self.meter.stop()
        self.audio_target = None
        self.probe_audio()
        if self.wanted and self.track:
            self.search()

    def probe_audio(self):
        if not self.wanted or not self.track or not self.track.get("playing") or self.track.get("stale"):
            if self.audio_target:
                self.meter.stop()
                self.audio_target = None
            return
        if self.audio_probe.state() != QProcess.ProcessState.NotRunning:
            return
        self.audio_probe.setProcessEnvironment(self.audio_environment())
        self.audio_probe.start(sys.executable, ["-m", "singlayer.worker", "audio-target"])
        self.audio_probe.write(json.dumps({"title": self.track["title"]}).encode())
        self.audio_probe.closeWriteChannel()

    def audio_probe_finished(self, *_):
        try:
            result = json.loads(bytes(self.audio_probe.readAllStandardOutput()))
            target = result.get("target")
            if not target:
                self.meter.setToolTip(
                    result.get(
                        "fatal", "No hay un flujo de navegador identificable; no se captura el escritorio."
                    )
                )
        except (ValueError, AttributeError):
            target = None
        if not self.wanted or not self.track or not self.track.get("playing"):
            target = None
        if target != self.audio_target:
            self.meter.stop()
            self.audio_target = target
            if target:
                self.meter.start(target)
        elif target and self.meter.process.state() == QProcess.ProcessState.NotRunning:
            self.meter.start(target)

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
        if self.closing:
            reply.deleteLater()
            return
        try:
            data = json.loads(bytes(reply.readAll()))
            if data.get("service") != "singlayer" or data.get("api_version") != 2:
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            self.online = False
            self.connection.setText("○ Conector apagado o antiguo")
            if self.track:
                self.cancel_job()
                self.stop_live(reset=True)
                self.track = self.document = None
                self.publish()
                self.title.setText("Sin conexión")
                self.cover.clear()
                self.cover.setText("♫")
            self.activity.setText(self.bridge_error or "Conectando con tu navegador…")
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
        self.browser_badge.setPixmap(self.browser.itemIcon(self.browser.currentIndex()).pixmap(20, 20))
        self.browser_badge.setToolTip(self.connection.text())
        self.connection.hide()
        self.extension_button.setVisible(not count)
        track = data.get("track")
        identity, previous = track.get("id") if track else None, self.track.get("id") if self.track else None
        if identity != previous:
            self.stop_live(reset=True)
            self.observed_document = None
            self.clock_anchors = {}
            self.automatic_clock = None
            self.calibration_anchor = None
            self.calibrating = False
            self.cancel_ai()
            self.guide = None
            self.cancel_job()
            self.document, self.plain, self.cover_revision = None, "", None
            self.cover.clear()
            self.cover.setText("♫")
            self.cover_attempts.clear()
            self.events.clear()
            for spin, value in ((self.offset, 0), (self.speed, 1)):
                spin.blockSignals(True)
                spin.setValue(value)
                spin.blockSignals(False)
        import time

        now = time.monotonic()
        if track and self.track and identity == previous and self.clock_observed_at is not None:
            elapsed = now - self.clock_observed_at if self.track.get("playing") else 0
            if abs(track.get("position", 0) - self.track.get("position", 0) - elapsed) > 1.5:
                self.stop_live()
                self.live_document = self.live_cache.get(self.live_cache_key())
                if self.job:
                    self.cancel_job()
                    self.resume_search = True
        self.clock_observed_at = now
        self.track = track
        if not track:
            self.title.setText("Esperando música")
            self.artist.setText("Recarga la pestaña tras instalar la extensión")
            self.clock.setText("— : —")
            self.timeline.setValue(0)
            self.publish()
            return
        if not track.get("playing") or track.get("stale"):
            self.stop_live()
        else:
            self.start_live()
        self.title.setText(track["title"])
        self.artist.setText(track.get("artist", ""))
        self.source_label.setText(track.get("source", "NAVEGADOR").upper())
        position, duration = int(track.get("position", 0)), int(track.get("duration", 0))
        self.clock.setText(
            f"{position // 60}:{position % 60:02d} / {duration // 60}:{duration % 60:02d}"
            + (" · reloj detenido" if track.get("stale") else " · pausa" if not track.get("playing") else "")
        )
        self.timeline.setValue(int(1000 * min(position / duration, 1)) if duration else 0)
        revision = track.get("cover") or safe_cover_url(track.get("cover_url"))
        if revision and revision != self.cover_revision and self.cover_attempts.get(revision, 0) < 3:
            self.fetch_cover(revision, identity)
        if self.job and (not track.get("playing") or track.get("stale")):
            self.cancel_job()
            self.resume_search = True
            self.activity.setText("En pausa")
        if self.wanted and (
            identity != previous
            or (getattr(self, "resume_search", False) and track.get("playing") and not track.get("stale"))
        ):
            self.resume_search = False
            self.search()
        self.publish()

    def fetch_cover(self, revision, identity):
        self.cover_revision = revision
        self.cover_attempts[revision] = self.cover_attempts.get(revision, 0) + 1
        if self.cover_reply:
            self.cover_reply.abort()
        direct = safe_cover_url(revision)
        request = QNetworkRequest(QUrl(direct or f"http://127.0.0.1:8975/cover?rev={revision}"))
        request.setAttribute(
            QNetworkRequest.Attribute.RedirectPolicyAttribute,
            QNetworkRequest.RedirectPolicy.ManualRedirectPolicy,
        )
        request.setTransferTimeout(3000)
        reply = self.network.get(request)
        self.cover_reply = reply
        reply.downloadProgress.connect(lambda received, _: reply.abort() if received > 1_500_000 else None)

        def done():
            raw = bytes(reply.readAll())
            loaded = False
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
                        loaded = True
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
                if not loaded:
                    self.cover_revision = None
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
        source_document = self.live_document or self.document
        if self.automatic_clock and self.document:
            source_document = {**self.document, "source": "audio-clock",
                               "sourceName": "Reloj estimado automáticamente · tres referencias o más"}
            adjustment = self.automatic_clock["offset"], self.automatic_clock["speed"]
        elif self.live_document:
            adjustment = (0, 1)
        if self._source_document is not source_document or self._adjustment != adjustment:
            self._source_document = source_document
            self._adjustment = adjustment
            key = tuple(line["text"] for line in (source_document or {}).get("lines", []))
            guided_document = source_document
            if self.reading_mode.currentIndex() and self.guide_key == key:
                guided_document = apply_guide(
                    source_document, self.guide, self.reading_mode.currentIndex() == 2
                )
            self._adjusted_document = adjusted_document(
                guided_document, *adjustment, duration=(self.track or {}).get("duration") or None
            )
        self.link.update(self.track, self._adjusted_document)
        lines = (self._adjusted_document or {}).get("lines", [])
        position = (self.track or {}).get("position", 0)
        current = next((line for line in reversed(lines) if line["start"] <= position), None)
        if self.live_document and not self.automatic_clock and current and current.get("end", position) < position - 3:
            current = None

        def display_text(line):
            return line["text"] + ("\n" + line["translation"] if line.get("translation") else "")

        self.lyric_preview.setText(display_text(current) if current else "")
        if self._visible_document is not self._adjusted_document:
            self._visible_document = self._adjusted_document
            self.lyric_lines.clear()
            def timestamp(value):
                minutes, seconds = divmod(value, 60)
                return f"{int(minutes):02d}:{seconds:05.2f}"

            self.lyric_lines.addItems([
                f"{timestamp(line['start'])} – {timestamp(line['end'])}  {display_text(line)}"
                if line.get("end") is not None else f"{timestamp(line['start'])}  {display_text(line)}"
                for line in lines
            ])
        row = next((i for i in range(len(lines) - 1, -1, -1) if lines[i]["start"] <= position), -1)
        if row != self.lyric_lines.currentRow():
            self.lyric_lines.setCurrentRow(row)
            if row >= 0:
                self.lyric_lines.scrollToItem(
                    self.lyric_lines.item(row), QAbstractItemView.ScrollHint.PositionAtCenter
                )

    def toggle_lines(self, enabled):
        self.lyric_preview.setVisible(not enabled)
        self.lyric_lines.setVisible(enabled)
        self.publish()

    def align_visible_line(self, item):
        if self.live_document:
            self.stop_live(reset=True)
            self.publish()
            self.activity.setText("Letra original restaurada · selecciona la línea para ajustar")
            return
        self.stop_live(reset=True)
        visible_row = self.lyric_lines.row(item)
        visible = (self._adjusted_document or {}).get("lines", [])
        chosen_id = visible[visible_row].get("id") if 0 <= visible_row < len(visible) else None
        row = next((index for index, line in enumerate((self.document or {}).get("lines", []))
                    if chosen_id is not None and line.get("id") == chosen_id), visible_row)
        if self.document and self.track and 0 <= row < len(self.document["lines"]):
            if self.calibrating:
                self.record_anchor(row)
                return
            self.offset.setValue(
                self.document["lines"][row]["start"] - self.track["position"] * self.speed.value()
            )
            self.activity.setText("Letra alineada con este momento")

    def begin_calibration(self):
        self.automatic_clock = None
        self.stop_live(reset=True)
        if not self.document:
            self.activity.setText("Primero hace falta una letra con tiempos")
            return
        self.publish()
        self.calibrating = True
        self.calibration_anchor = None
        self.lines_button.setChecked(True)
        self.activity.setText("Doble clic en la línea que empieza a sonar; después marca otra más adelante")

    def record_anchor(self, row):
        if not self.track.get("playing") or self.track.get("stale"):
            self.activity.setText("Reproduce la música antes de marcar una referencia")
            return
        point = self.track["position"], self.document["lines"][row]["start"]
        if self.calibration_anchor is None:
            self.calibration_anchor = point
            self.activity.setText("Primera referencia guardada · marca otra línea dentro de al menos 15 s")
            return
        try:
            offset, speed = calibrate(self.calibration_anchor, point)
        except ValueError as error:
            self.activity.setText(str(error))
            return
        self.offset.blockSignals(True)
        self.speed.blockSignals(True)
        self.offset.setValue(offset)
        self.speed.setValue(speed)
        self.offset.blockSignals(False)
        self.speed.blockSignals(False)
        self.calibrating = False
        self.calibration_anchor = None
        self.publish()
        self.save_alignment()
        self.activity.setText(f"Sincronización calibrada · {speed:.3f} ×")

    def alignment_key(self):
        import hashlib

        if not self.track or not self.document:
            return None
        identity = [self.track.get(key) for key in ("source", "title", "artist", "duration")]
        identity.append([self.document.get("source"), self.document.get("title"), self.document.get("artist"),
                         [(line["text"], line["start"], line.get("end")) for line in self.document["lines"]]])
        return hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()

    def save_alignment(self):
        key = self.alignment_key()
        if not key:
            return
        try:
            stored = json.loads(self.settings.value("alignments", "{}"))
            if not isinstance(stored, dict):
                stored = {}
        except (ValueError, TypeError):
            stored = {}
        stored.pop(key, None)
        if (self.offset.value(), self.speed.value()) != (0, 1):
            stored[key] = [self.offset.value(), self.speed.value()]
        while len(stored) > 32:
            stored.pop(next(iter(stored)))
        self.settings.setValue("alignments", json.dumps(stored))

    def restore_alignment(self):
        try:
            stored = json.loads(self.settings.value("alignments", "{}"))
            offset, speed = stored.get(self.alignment_key(), [0, 1])
            if not (-3600 <= offset <= 3600 and .5 <= speed <= 2):
                return
        except (ValueError, TypeError, AttributeError):
            return
        for spin, value in ((self.offset, offset), (self.speed, speed)):
            spin.blockSignals(True)
            spin.setValue(value)
            spin.blockSignals(False)

    def alignment_changed(self, *_):
        self.automatic_clock = None
        self.stop_live(reset=True)
        self.save_alignment()
        self.publish()

    def reset_alignment(self):
        self.automatic_clock = None
        self.calibrating = False
        self.calibration_anchor = None
        self.offset.setValue(0)
        self.speed.setValue(1)
        self.publish()
        self.activity.setText("Tiempos originales restaurados")

    def live_cache_key(self):
        if not self.track:
            return None
        return (self.track.get("id"), self.track.get("title"), self.track.get("artist"),
                self.track.get("duration"), tuple(line["text"] for line in (self.document or {}).get("lines", [])))

    def remember_live(self):
        key = self.live_cache_key()
        if key and self.live_document:
            self.live_cache.pop(key, None)
            self.live_cache[key] = self.live_document
            while len(self.live_cache) > 16:
                self.live_cache.pop(next(iter(self.live_cache)))

    def stop_live(self, reset=False):
        self.live_epoch += 1
        process, self.live_job = self.live_job, None
        if process:
            self.retiring_jobs.add(process)
            process.terminate()
            QTimer.singleShot(3800, lambda: process.kill() if process in self.retiring_jobs else None)
        if reset:
            self.live_enabled = False
            self.live_document = None
            self.live_retry_at = 0

    def start_live(self):
        import time

        if (not self.live_enabled or not self.wanted or self.live_job or not self.track
                or not self.track.get("playing") or self.track.get("stale")
                or time.monotonic() < self.live_retry_at):
            return
        from .transcriber_runtime import selected_engine

        try:
            engine = selected_engine()
        except (ValueError, KeyError, OSError) as error:
            self.activity.setText(str(error))
            self.live_enabled = False
            return
        if engine.get("ready") is False:
            self.activity.setText("CrisperWhisper no instalado · ejecuta scripts/setup-crisper.sh")
            self.live_enabled = False
            return
        if self.crisper.state() == QProcess.ProcessState.NotRunning:
            self.crisper.start("bash", [str(ROOT / "scripts/run-transcriber.sh")])
        process = QProcess(self)
        self.live_job = process
        epoch = self.live_epoch
        output = bytearray()
        self.activity.setText(f"Escuchando fragmentos · {engine['label']}")

        def consume():
            from .alignment import align_fragment, estimate_clock
            from .live_transcription import merge_transcript

            output.extend(bytes(process.readAllStandardOutput()))
            if len(output) > 1_000_000:
                self.stop_live()
                return
            while b"\n" in output:
                line, _, rest = output.partition(b"\n")
                output[:] = rest
                if epoch != self.live_epoch:
                    continue
                try:
                    event = json.loads(line)
                    if "transcript" in event:
                        doc = event["transcript"]
                        self.observed_document = merge_transcript(self.observed_document, doc)
                        if self.document:
                            choices = self.catalog_candidates or [self.document]
                            aligned = [align_fragment(doc, candidate) for candidate in choices]
                            aligned = [candidate for candidate in aligned if candidate]
                            signatures = {tuple(line["text"].casefold() for line in candidate["lines"]) for candidate in aligned}
                            doc = max(aligned, key=lambda candidate: len(candidate["lines"])) if len(signatures) == 1 else None
                            clock = estimate_clock(event["transcript"], self.document, self.clock_anchors)
                            title = (self.track or {}).get("title", "").casefold()
                            structurally_edited = any(word in title for word in ("remix", "mashup", "loop", "cut", "snippet"))
                            self.automatic_clock = clock if not structurally_edited else None
                            if not doc and not self.automatic_clock:
                                # Repeated choruses cannot establish a catalog occurrence,
                                # but the words measured in this window still have a clock.
                                doc = event["transcript"]
                        if doc:
                            self.live_document = merge_transcript(self.live_document, doc)
                        self.remember_live()
                        if self.reading_mode.currentIndex():
                            self.reading_changed()
                        self.activity.setText(
                            f"Reloj automático estimado · {self.automatic_clock['anchors']} referencias · {self.automatic_clock['speed']:.3f} ×"
                            if self.automatic_clock else
                            f"{'Alineación' if doc and doc.get('source') == 'audio-aligned' else 'Transcripción'} estimada · retraso {event['lag']:.1f} s"
                        )
                        self.publish()
                    elif event.get("discontinuity"):
                        self.live_document = self.live_cache.get(self.live_cache_key())
                        self.publish()
                    elif "fatal" in event:
                        self.activity.setText(event["fatal"])
                        self.live_retry_at = time.monotonic() + 30
                    elif "live_status" in event:
                        self.activity.setText(event["live_status"])
                except (ValueError, KeyError, TypeError):
                    self.activity.setText("Respuesta de transcripción inválida")

        finished = False

        def finish(*_):
            nonlocal finished
            if finished:
                return
            finished = True
            consume()
            if epoch == self.live_epoch:
                self.live_job = None
                self.live_retry_at = max(self.live_retry_at, time.monotonic() + 1)
            self.retiring_jobs.discard(process)
            process.deleteLater()

        process.readyReadStandardOutput.connect(consume)
        process.finished.connect(finish)
        def failed(error):
            if error == QProcess.ProcessError.FailedToStart:
                if epoch == self.live_epoch:
                    self.activity.setText("No se pudo iniciar la transcripción local")
                    self.live_retry_at = time.monotonic() + 30
                finish()

        process.errorOccurred.connect(failed)
        payload = json.dumps({"track": dict(self.track)}).encode()
        process.started.connect(lambda: (process.write(payload), process.closeWriteChannel()))
        process.setProcessEnvironment(self.audio_environment())
        process.start(sys.executable, ["-m", "singlayer.worker", "live"])

    def search(self, recognize=False, override=None):
        self.observed_document = None
        self.clock_anchors = {}
        self.automatic_clock = None
        if not self.track:
            self.activity.setText("Primero conecta una canción")
            return
        if recognize and (not self.track.get("playing") or self.track.get("stale")):
            self.activity.setText("Reproduce una canción para reconocerla")
            return
        if self.installer.state() != QProcess.ProcessState.NotRunning:
            return
        self.cancel_job()
        self.stop_live(reset=True)
        self.events.clear()
        cache_key = (self.track["title"], self.track.get("artist", ""), self.track.get("duration"))
        if not recognize and override is None and cache_key in self.result_cache:
            self.job_event({"finished": True, "result": self.result_cache[cache_key]})
            self.activity.setText("Letra recuperada de esta sesión")
            return
        self.document, self.plain = None, ""
        self.cancel_ai()
        self.guide = None
        self.publish()
        self.progress.setRange(0, 0)
        self.activity.setText("Reconociendo audio…" if recognize else "Buscando letras…")
        process = QProcess(self)
        self.job = process
        epoch = self.job_epoch
        data = {
            "track": override or self.track,
            "recognize": recognize,
            "audio_allowed": bool(self.track.get("playing") and not self.track.get("stale")),
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
        process.setProcessEnvironment(self.audio_environment())
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
            self.calibrating = False
            self.calibration_anchor = None
            result = event["result"]
            self.document, self.plain = result.get("document"), result.get("plain", "")
            self.catalog_candidates = result.get("candidates", [])
            self.restore_alignment()
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
            self.activity.setText(
                (
                    f"Identidad confirmada · {result['evidence']['matches']}/{result['evidence']['samples']} muestras · timing por comprobar"
                    if result.get("evidence", {}).get("confirmed")
                    else f"Letra candidata · {self.document['source']} · identidad/timing sin confirmar"
                )
                if self.document
                else "Letra encontrada sin sincronización"
                if self.plain
                else self.search_failure()
            )
            self.progress.setRange(0, 100)
            self.progress.setValue(100 if self.document or self.plain else 0)
            self.live_document = self.live_cache.get(self.live_cache_key())
            self.publish()
            self.reading_changed()
            from .workflow import search_identity

            self.live_enabled = (not self.document
                                 or search_identity(self.track or {"title": ""})["edited"]
                                 or not (self.track or {}).get("artist", "").strip()
                                 or (self.track or {}).get("source") == "SoundCloud"
                                 or bool(result.get("recognized"))
                                 or any(line["start"] >= (self.track or {}).get("duration", 0)
                                        for line in (self.document or {}).get("lines", [])
                                        if (self.track or {}).get("duration", 0) > 0)
                                 or len(self.catalog_candidates) > 1)
            if (self.offset.value(), self.speed.value()) != (0, 1):
                self.live_enabled = False
                self.live_document = None
                self.publish()
            self.start_live()
            return
        self.events[event["stage"]] = event
        if event["state"] == "running":
            self.activity.setText(event["detail"])

    def search_failure(self):
        failures = [event for event in self.events.values() if event["state"] in {"error", "missing"}]
        self.activity.setToolTip(
            "\n".join(f"{stage}: {event['detail']}" for stage, event in self.events.items())
        )
        if any(
            stage.startswith("shazam") and event["state"] in {"error", "missing"}
            for stage, event in self.events.items()
        ):
            return "Sin letra · reconocimiento de audio no disponible · detalles al pasar el cursor"
        if failures:
            return "Búsqueda incompleta: fallaron proveedores · detalles al pasar el cursor"
        return "Los proveedores consultados no encontraron letra · ajustes en ⋯"

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

    def choose_version(self):
        if not self.track:
            return
        identity = self.track["id"]
        dialog = QDialog(self)
        dialog.setWindowTitle("Otras versiones · LRCLIB")
        dialog.resize(560, 400)
        layout = QVBoxLayout(dialog)
        status = label("Buscando versiones…", "muted")
        listing = QListWidget()
        layout.addWidget(status)
        layout.addWidget(listing)
        documents = []
        process = QProcess(dialog)
        output = bytearray()

        def read():
            output.extend(bytes(process.readAllStandardOutput()))
            if len(output) > 4_000_000:
                process.kill()

        def finish(*_):
            read()
            try:
                result = json.loads(output)
                documents.extend(result.get("documents", []))
                listing.addItems(
                    [f"{doc['title']} — {doc['artist']} · {len(doc['lines'])} líneas" for doc in documents]
                )
                status.setText(
                    "Doble clic para usar una versión; puede requerir alinear tiempos."
                    if documents
                    else "Proveedor no disponible"
                    if result.get("failed") or result.get("fatal")
                    else "No hay versiones para este título"
                )
            except (ValueError, KeyError, TypeError):
                status.setText("No se pudo consultar las versiones")

        def select(item):
            if self.track and self.track["id"] == identity:
                self.cancel_job()
                self.cancel_ai()
                self.guide = None
                self.job_event({"finished": True, "result": {"document": documents[listing.row(item)]}})
                dialog.accept()

        listing.itemDoubleClicked.connect(select)
        process.readyReadStandardOutput.connect(read)
        process.finished.connect(finish)
        process.started.connect(
            lambda: (process.write(json.dumps({"track": self.track}).encode()), process.closeWriteChannel())
        )
        process.start(sys.executable, ["-m", "singlayer.worker", "alternatives"])
        deadline = QTimer(dialog)
        deadline.setSingleShot(True)
        deadline.timeout.connect(process.kill)
        deadline.start(25_000)
        dialog.exec()
        deadline.stop()
        terminate(process)

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

    def check_engines(self):
        importlib.invalidate_caches()
        missing = [
            name for name in ("syncedlyrics", "shazamio", "numpy", "espeakng_loader", "langid", "pykakasi") if importlib.util.find_spec(name) is None
        ]
        if sys.version_info >= (3, 13) and importlib.util.find_spec("audioop") is None:
            missing.append("audioop-lts")
        self.missing_engines = missing

    def install_engines(self):
        uv = shutil.which("uv")
        if not uv and (Path.home() / ".local/bin/uv").is_file():
            uv = str(Path.home() / ".local/bin/uv")
        if not uv:
            self.activity.setText("Falta uv · consulta la instalación del proyecto")
            return
        self.cancel_job()
        self.activity.setText("Preparando SingLayer por primera vez…")
        self.progress.setRange(0, 0)
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
            "Listo" if code == 0 else "No se pudo completar la preparación · revisa la conexión"
        )
        self.progress.setRange(0, 100)
        if self.wanted and self.track:
            self.search()

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
        self.stop_live(reset=True)
        terminate(self.crisper)
        self.cancel_ai()
        self.cancel_job()
        self.link.stop()
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
        self.closing = True
        self.timer.stop()
        self.audio_timer.stop()
        terminate(self.audio_probe)
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
