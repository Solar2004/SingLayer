#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .build/crisperwhisper/ready.json && -x .build/crisper-runtime/bin/python ]] || {
  echo 'CrisperWhisper not installed: bash scripts/setup-crisper.sh' >&2; exit 1;
}
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
exec .build/crisper-runtime/bin/python -m singlayer.crisper_service
