"""Installer argument and preservation contracts, without network or system writes."""
import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/install.sh"


def run_installer(tmp_path, *args):
    binaries = tmp_path / "bin"
    binaries.mkdir()
    # All preflight commands succeed; any attempt to clone is observable.
    for name in ("git", "uv", "cmake", "c++", "pkg-config", "ffmpeg", "pactl", "parec",
                 "glslc", "curl", "sha256sum", "rg", "python"):
        path = binaries / name
        path.write_text('#!/bin/sh\nif [ "$1" = clone ]; then echo unexpected-clone >&2; exit 97; fi\nexit 0\n')
        path.chmod(0o755)
    env = {**os.environ, "PATH": str(binaries) + ":" + os.environ["PATH"],
           "SINGLAYER_PYTHON": str(binaries / "python")}
    return subprocess.run(["bash", str(SCRIPT), *args], env=env, capture_output=True, text=True)


def test_check_mode_does_not_create_installation(tmp_path):
    prefix = tmp_path / "new install"
    result = run_installer(tmp_path, "--check", "--with-whisper", "--prefix", str(prefix))
    assert result.returncode == 0, result.stderr
    assert not prefix.exists()


def test_existing_directory_preserved_without_clone(tmp_path):
    prefix = tmp_path / "existing"
    prefix.mkdir()
    sentinel = prefix / "local-work"
    sentinel.write_text("keep")
    result = run_installer(tmp_path, "--prefix", str(prefix))
    assert result.returncode == 1
    assert "already exists" in result.stderr
    assert sentinel.read_text() == "keep"
    assert "unexpected-clone" not in result.stderr


def test_unknown_option_is_rejected(tmp_path):
    result = run_installer(tmp_path, "--erase")
    assert result.returncode == 2
    assert "Unknown option" in result.stderr


def test_relative_prefix_is_rejected(tmp_path):
    result = run_installer(tmp_path, "--prefix", "relative")
    assert result.returncode == 2
    assert "absolute" in result.stderr
