import hashlib
import json

import pytest

from singlayer import transcriber_runtime as runtime


def installed(tmp_path, monkeypatch, optimized=True):
    monkeypatch.setattr(runtime, "ROOT", tmp_path)
    binary = tmp_path / "server"
    model = tmp_path / "model"
    library = tmp_path / "library"
    patch = tmp_path / "patches/whisper-reuse-language-encoder.patch"
    patch.parent.mkdir()
    for path in (binary, model, library, patch):
        path.write_bytes(b"validated")
    config = {"backend": "whisper.cpp", "device": "vulkan",
              "model": "large-v3-turbo-q5_0", "binary": str(binary),
              "model_path": str(model)}
    if optimized:
        config.update(inference_profile="reuse-language-encoder-v1",
                      library_path=str(library),
                      library_sha256=hashlib.sha256(library.read_bytes()).hexdigest(),
                      build_patch_sha256=hashlib.sha256(patch.read_bytes()).hexdigest())
    ready = tmp_path / ".build/whisper/ready.json"
    ready.parent.mkdir(parents=True)
    ready.write_text(json.dumps(config))
    return library, patch


@pytest.mark.parametrize("optimized", [False, True])
def test_validated_runtime_and_legacy_installation(tmp_path, monkeypatch, optimized):
    installed(tmp_path, monkeypatch, optimized)
    assert runtime.selected_engine("whisper")["device"] == "vulkan"


@pytest.mark.parametrize("target", [0, 1])
def test_changed_optimized_build_is_rejected(tmp_path, monkeypatch, target):
    files = installed(tmp_path, monkeypatch)
    files[target].write_bytes(b"changed")
    with pytest.raises(ValueError, match="compilación validada"):
        runtime.selected_engine("whisper")
