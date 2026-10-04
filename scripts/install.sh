#!/usr/bin/env bash
# User-local installation. No sudo, browser-profile changes or automatic launch.
set -euo pipefail
release=v0.2.0
prefix="${XDG_DATA_HOME:-$HOME/.local/share}/singlayer/app"
with_whisper=false
check_only=false
while (($#)); do
  case "$1" in
    --with-whisper) with_whisper=true; shift ;;
    --check) check_only=true; shift ;;
    --prefix) [[ $# -ge 2 ]] || { echo 'Missing --prefix directory' >&2; exit 2; }; prefix="$2"; shift 2 ;;
    --help) echo 'Usage: install.sh [--with-whisper] [--check] [--prefix DIRECTORY]'; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done
[[ "$(uname -s)" == Linux ]] || { echo 'SingLayer requires Linux.' >&2; exit 1; }
missing=()
for dependency in git uv cmake c++ pkg-config ffmpeg pactl parec; do
  command -v "$dependency" >/dev/null || missing+=("$dependency")
done
python="${SINGLAYER_PYTHON:-/usr/bin/python3}"
"$python" -c 'import sys; assert sys.version_info >= (3, 11); import PyQt6.QtCore, PyQt6.QtWidgets, PyQt6.QtWebSockets' >/dev/null 2>&1 || missing+=('Python 3.11+ with system PyQt6 and QtWebSockets')
if $with_whisper; then
  for dependency in glslc curl sha256sum rg; do
    command -v "$dependency" >/dev/null || missing+=("$dependency")
  done
fi
if ((${#missing[@]})); then
  printf 'Missing requirement: %s\n' "${missing[@]}" >&2
  echo 'See https://github.com/Solar2004/SingLayer/blob/v0.2.0/docs/INSTALL.md' >&2
  exit 1
fi
if $check_only; then
  echo 'Executable/Python checks passed. Setup additionally checks native Qt/LayerShellQt build dependencies.'
  exit 0
fi
[[ "$prefix" == /* ]] || { echo '--prefix must be an absolute directory.' >&2; exit 2; }
if [[ -e "$prefix" ]]; then
  echo "Installation directory already exists: $prefix" >&2
  echo 'Use another --prefix; existing installations and local changes are preserved.' >&2
  exit 1
fi
mkdir -p "$(dirname "$prefix")"
git clone --branch "$release" --depth 1 https://github.com/Solar2004/SingLayer.git "$prefix"
bash "$prefix/scripts/setup.sh"
if $with_whisper; then
  bash "$prefix/scripts/setup-whisper-vulkan.sh"
fi
# Desktop Entry quoting handles paths containing spaces and reserved characters.
"$python" - "$prefix" <<'PY'
import os
import shlex
import sys
from pathlib import Path
root = Path(sys.argv[1])
data = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share'))
bin_dir = Path.home() / '.local/bin'
bin_dir.mkdir(parents=True, exist_ok=True)
launcher = bin_dir / 'singlayer'
if launcher.exists() or launcher.is_symlink():
    print(f'Existing launcher preserved: {launcher}')
else:
    launcher.write_text('#!/bin/sh\nexec ' + shlex.quote(str(root / '.venv/bin/singlayer')) + ' "$@"\n')
    launcher.chmod(0o755)
applications = data / 'applications'
applications.mkdir(parents=True, exist_ok=True)
path = applications / 'singlayer.desktop'
if path.exists():
    print(f'Existing desktop shortcut preserved: {path}')
else:
    executable = str(root / '.venv/bin/singlayer')
    for char in ('\\', '"', '`', '$'):
        executable = executable.replace(char, '\\' + char)
    executable = executable.replace('%', '%%')
    path.write_text('[Desktop Entry]\nType=Application\nName=SingLayer\n'
                    'Comment=Browser music with synchronized desktop lyrics\n'
                    f'Exec="{executable}" app\nIcon=audio-headphones\nTerminal=false\nCategories=AudioVideo;Music;\n')
print(f'Installed. Open SingLayer from your application menu, or run {root / ".venv/bin/singlayer"} app')
print(f'Browser configuration: {root / "docs/INSTALL.md"}')
PY
