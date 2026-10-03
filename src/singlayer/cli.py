"""Launch the connector and unmodified upstream overlay with isolated settings."""

import argparse
import asyncio
import json
import logging
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

from .bridge import serve


def overlay_environment():
    env = os.environ.copy()
    base = Path(env.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "singlayer"
    config = base / "kotonoha" / "config.json"
    if not config.exists():
        config.parent.mkdir(parents=True, exist_ok=True)
        preset = {
            "anchor_top": False,
            "margin_edge": 100,
            "font_size": 34,
            "context_font_size": 22,
            "panel_style": "text",
            "opacity": 0.0,
            "fx_glow": True,
            "fx_word_pop": True,
            "fx_intensity": "subtle",
            "accent_start": "#8BDFFF",
            "accent_end": "#E1CEFF",
            "accent_sweep": "#FFFFFF",
            "show_translation": False,
            "ui_language": "en",
            "lyrics_sources": ["lrclib", "netease", "kugou"],
            "display_sources": ["mpris", "adapter"],
            "player_lock": "org.mpris.MediaPlayer2.singlayer",
        }
        with config.open("x") as output:
            json.dump(preset, output, indent=2)
    env["XDG_CONFIG_HOME"] = str(base)
    env["XDG_CACHE_HOME"] = str(Path(env.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "singlayer")
    # Let Qt choose the installed platform plugin. Never force X11 on Wayland.
    return env


def launch_overlay():
    executable = Path(sys.executable).parent / "kotonoha"
    if not executable.is_file():
        raise SystemExit("Kotonoha is missing. Run scripts/setup.sh first.")
    return subprocess.Popen([str(executable)], env=overlay_environment())


def main():
    parser = argparse.ArgumentParser(description="SingLayer: browser music → native karaoke")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("start", help="Run bridge and upstream overlay together")
    bridge = sub.add_parser("bridge", help="Run just the WebNowPlaying → MPRIS bridge")
    bridge.add_argument("--port", type=int, default=8975)
    sub.add_parser("overlay", help="Run the upstream Kotonoha overlay")
    sub.add_parser("recognize", help="Open SongRec without starting audio capture")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if args.action == "bridge":
        asyncio.run(serve(args.port))
    elif args.action == "overlay":
        raise SystemExit(launch_overlay().wait())
    elif args.action == "recognize":
        executable = shutil.which("songrec")
        if not executable:
            raise SystemExit("Install SongRec from your distribution or Flathub first; see README.")
        raise SystemExit(subprocess.call([executable, "gui-norecording"]))
    else:
        children = []

        def stop(signum, frame):
            raise KeyboardInterrupt

        signal.signal(signal.SIGTERM, stop)
        try:
            children.append(subprocess.Popen([sys.executable, "-m", "singlayer", "bridge"]))
            children.append(launch_overlay())
            while all(child.poll() is None for child in children):
                try:
                    children[0].wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    continue
        except KeyboardInterrupt:
            pass
        finally:
            for child in children:
                if child.poll() is None:
                    child.terminate()
            for child in children:
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
