"""Download an immutable model revision and convert once, then publish readiness."""
import json
import sys
from pathlib import Path


def main():
    import numpy as np
    from crisperwhisper import CrisperWhisperModel
    from crisperwhisper.converter import ensure_ct2_model
    from huggingface_hub import model_info, snapshot_download

    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    from singlayer.crisper_model import restore_runtime_config

    directory = root / ".build/crisperwhisper"
    directory.mkdir(parents=True, exist_ok=True)
    identity = "nyralabs/CrisperWhisper2.0_small"
    lock = directory / "model-lock.json"
    if lock.is_file():
        revision = json.loads(lock.read_text())["revision"]
    else:
        revision = model_info(identity).sha
        lock.write_text(json.dumps({"model": identity, "revision": revision}))
    snapshot = snapshot_download(identity, revision=revision, cache_dir=str(directory / "hf"))
    converted = ensure_ct2_model(snapshot, quantization="int8", cache_dir=directory / "ct2")

    restore_runtime_config(converted)
    model = CrisperWhisperModel(str(converted), backend="ct2", device="cpu", compute_type="int8")
    # Loading alone did not catch missing native language metadata. Exercise the
    # same acoustic detector used by the service before publishing readiness.

    model._engine.model.detect_language(model._engine.extract_features(np.zeros(16000, dtype=np.float32)))
    config = {"model": identity, "revision": revision, "model_path": str(Path(converted).resolve()), "device": "cpu", "package": "2.0.3"}
    temporary = directory / "ready.json.part"
    temporary.write_text(json.dumps(config, indent=2))
    temporary.replace(directory / "ready.json")
    print("CrisperWhisper ready: small, CPU int8, word timestamps")


if __name__ == "__main__":
    main()
