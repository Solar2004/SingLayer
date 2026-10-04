#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
uv pip install --python .venv/bin/python -r requirements-engines.txt
# Native ShazamIO wheels run in the known-compatible Python 3.12 runtime.
bash scripts/setup-recognizer.sh
