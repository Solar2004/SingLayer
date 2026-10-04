"""Low-latency FFT of one explicitly selected browser stream."""

import shutil
import time

from PyQt6.QtCore import QProcess, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QWidget

from .browser_audio import capture_args


def spectrum(pcm, bands=32):
    import numpy as np

    samples = np.frombuffer(pcm[-2048:], dtype="<i2").astype(float) / 32768
    if len(samples) < 1024:
        return [0.0] * bands
    power = abs(np.fft.rfft(samples * np.hanning(len(samples)))) / len(samples)
    edges = np.geomspace(2, len(power), bands + 1).astype(int)
    return [
        float(np.clip((20 * np.log10(max(float(power[a : max(a + 1, b)].max()), 1e-8)) + 65) / 65, 0, 1))
        for a, b in zip(edges[:-1], edges[1:])
    ]


class AudioMeter(QWidget):
    failure = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(64)
        self.values = [0.0] * 32
        self.pcm = bytearray()
        self.last_audio = 0.0
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self.read)
        self.process.errorOccurred.connect(lambda _: self.failure.emit("Captura no disponible"))
        self.process.finished.connect(self.finished)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.draw_frame)
        self.timer.start(60)
        self.setToolTip("Audio aislado del navegador; nunca el micrófono ni la mezcla del escritorio.")

    def start(self, target=None):
        if not target:
            return
        if self.process.state() != QProcess.ProcessState.NotRunning:
            return
        if not shutil.which("parec"):
            self.failure.emit("Falta parec (pulseaudio-utils / libpulse)")
            return
        self.process.start("parec", capture_args(target))

    def read(self):
        self.pcm.extend(bytes(self.process.readAllStandardOutput()))
        self.pcm = self.pcm[-2048:]
        self.last_audio = time.monotonic()

    def draw_frame(self):
        if self.pcm and time.monotonic() - self.last_audio < 0.25:
            try:
                self.values = spectrum(bytes(self.pcm[: len(self.pcm) // 2 * 2]))
            except ImportError:
                self.failure.emit("Falta NumPy para el espectro")
                self.stop()
        else:
            self.values = [value * 0.7 for value in self.values]
        self.update()

    def finished(self, code, status):
        if code:
            self.failure.emit("No se pudo capturar la salida de audio")

    def stop(self):
        self.process.terminate()
        if not self.process.waitForFinished(800) and self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
            self.process.waitForFinished(800)
        self.pcm.clear()
        self.values = [0.0] * 32
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        step = self.width() / len(self.values)
        painter.setPen(QColor("#d9d9d9"))
        painter.setBrush(QColor("#d9d9d9"))
        for index, value in enumerate(self.values):
            height = max(2, int(value * (self.height() - 8)))
            painter.drawRoundedRect(
                int(index * step + 2), (self.height() - height) // 2, max(2, int(step - 4)), height, 2, 2
            )
