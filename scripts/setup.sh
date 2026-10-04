#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
command -v uv >/dev/null || { echo 'Install uv: https://docs.astral.sh/uv/'; exit 1; }
git submodule update --init upstream/kotonoha upstream/webnowplaying
# System PyQt6 and system Qt must match the native LayerShellQt build.
SINGLAYER_PYTHON="${SINGLAYER_PYTHON:-/usr/bin/python3}"
"$SINGLAYER_PYTHON" -c 'from PyQt6.QtCore import QT_VERSION_STR; print("System Qt:", QT_VERSION_STR)'
uv venv --system-site-packages --python "$SINGLAYER_PYTHON" .venv
uv pip install --python .venv/bin/python -r requirements.lock
uv pip install --python .venv/bin/python --no-deps -e .
uv pip install --python .venv/bin/python --no-deps ./upstream/kotonoha
uv pip install --python .venv/bin/python -r requirements-engines.txt
bash scripts/setup-recognizer.sh
SINGLAYER_SOURCE_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/singlayer/source-link"
install -d "$SINGLAYER_SOURCE_DIR"
install -m 644 browser/source-link/*.js browser/source-link/manifest.json "$SINGLAYER_SOURCE_DIR/"
printf 'Automatic source-link extension prepared in %s\n' "$SINGLAYER_SOURCE_DIR"
echo 'Ready. Add a WebNowPlaying custom adapter on port 8975, then run .venv/bin/singlayer app'
