"""Render the unmodified upstream overlay with original demo text (no network)."""

import argparse
from pathlib import Path

from kotonoha.config import Config
from kotonoha.display.models import DisplayFrame, DisplayState, LineProgress, WordProgress
from kotonoha.lyrics.models import LyricLine, LyricsDocument, LyricWord, TimingKind
from kotonoha.platform.native import LayerShellController, default_package_dir
from kotonoha.platform.window_platform import DefaultOverlayPlatformFactory
from kotonoha.ui.overlay import LyricsOverlay
from kotonoha.ui.overlay.state import LyricsState
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="docs/overlay-preview.png")
    args = parser.parse_args()
    app = QApplication([])
    config = Config.from_dict(
        {
            "font_size": 34,
            "context_font_size": 22,
            "panel_style": "text",
            "show_translation": False,
            "fx_glow": True,
            "fx_word_pop": True,
            "fx_animate": False,
            "accent_start": "#8BDFFF",
            "accent_end": "#E1CEFF",
            "accent_sweep": "#FFFFFF",
            "ui_language": "en",
        }
    )
    controller = LayerShellController(default_package_dir(), app.platformName(), "KDE")
    factory = DefaultOverlayPlatformFactory(
        controller, platform_name=app.platformName(), current_desktop="KDE"
    )
    state = LyricsState()
    overlay = LyricsOverlay(state, config, platform_factory=factory)
    previous = LyricLine(0, "previous", 0, 4, "La ciudad baja la voz", "")
    words = tuple(LyricWord(4 + i, 5 + i, text) for i, text in enumerate(["y ", "yo ", "sigo ", "cantando"]))
    current = LyricLine(1, "current", 4, 8, "y yo sigo cantando", "", words)
    following = LyricLine(2, "next", 8, 12, "hasta encender el amanecer", "")
    doc = LyricsDocument("singlayer-demo", timing=TimingKind.WORD, lines=(previous, current, following))
    state.update(
        DisplayFrame(
            DisplayState.LYRICS_AVAILABLE,
            document=doc,
            current_time=6.4,
            previous=previous,
            current=current,
            next=following,
            line_progress=LineProgress("current", 0.6),
            word_progress=WordProgress("current", (1.0, 1.0, 0.4, 0.0), 2),
        )
    )
    overlay.show()

    def save():
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        if not overlay.grab().save(str(output)):
            raise RuntimeError("Cannot save preview")
        print(f"Rendered upstream overlay: platform={app.platformName()} layer_shell={controller.available}")
        overlay.close()
        app.quit()

    QTimer.singleShot(1000, save)
    app.exec()


if __name__ == "__main__":
    main()
