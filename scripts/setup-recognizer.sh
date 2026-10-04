#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export UV_PYTHON_INSTALL_DIR="$PWD/.build/python"
export UV_CACHE_DIR="$PWD/.build/uv-cache"
uv venv --python 3.12 .build/recognizer
uv pip install --python .build/recognizer/bin/python shazamio==0.8.1
.build/recognizer/bin/python -c 'from shazamio import Shazam; print("Recognition runtime ready")'
