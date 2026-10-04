"""Render the actual Qt panel in an explicitly labelled demo, without services."""

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from singlayer.dashboard import Dashboard


class Preview(Dashboard):
    def bootstrap(self):
        pass

    def poll(self):
        pass


app = QApplication([])
panel = Preview()
panel.timer.stop()
panel.audio_timer.stop()
panel.title.setText("Tu música, tu voz")
panel.artist.setText("Vista de demostración · sin reproducción")
panel.connection.hide()
panel.extension_button.hide()
panel.activity.setText("La búsqueda empieza al reproducir música")
panel.lyric_preview.setText("La letra aparece aquí")
panel.show()


def save():
    assert panel.grab().save("docs/dashboard-preview.png")
    panel.close()
    app.quit()


QTimer.singleShot(150, save)
app.exec()
