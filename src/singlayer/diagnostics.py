"""Small rotating local diagnostic log: no lyrics, audio or model responses."""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def log_path():
    return (
        Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "singlayer" / "diagnostics.log"
    )


def record(component, code, *, status=None):
    # An unavailable log directory must never break playback or an error handler.
    try:
        path = log_path()
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Each process has its own handler lifecycle; never log supplied content.
        handler = RotatingFileHandler(path, maxBytes=131072, backupCount=1, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))

        def safe(value):
            return "".join(c for c in str(value) if c.isalnum() or c in "_-.")[:80]

        event = logging.LogRecord(
            "singlayer",
            logging.WARNING,
            "",
            0,
            f"{safe(component)} {safe(code)} status={safe(status)}",
            (),
            None,
        )
        try:
            handler.handle(event)
        finally:
            handler.close()
    except OSError:
        pass
