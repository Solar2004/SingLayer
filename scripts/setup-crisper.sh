#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export UV_PYTHON_INSTALL_DIR="$PWD/.build/python"
export UV_CACHE_DIR="$PWD/.build/uv-cache"
# HTTP completed here when the optional native Xet transfer stalled.
export HF_HUB_DISABLE_XET="${HF_HUB_DISABLE_XET:-1}"
command -v uv >/dev/null || { echo 'Install uv first.' >&2; exit 1; }
uv venv --python 3.12 --allow-existing .build/crisper-runtime
# CPU-only torch is used once to convert weights; no NVIDIA libraries on RX590.
uv pip install --python .build/crisper-runtime/bin/python --index-url https://download.pytorch.org/whl/cpu 'torch>=2.4'
uv pip install --python .build/crisper-runtime/bin/python -r requirements-crisper.txt
.build/crisper-runtime/bin/python scripts/prepare-crisper.py
