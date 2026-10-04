#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
if [[ "${SINGLAYER_ENGINE:-auto}" != crisper && -f .build/whisper/ready.json ]]; then
  exec .venv/bin/python -m singlayer.whisper_service
fi
exec bash scripts/run-crisper.sh
