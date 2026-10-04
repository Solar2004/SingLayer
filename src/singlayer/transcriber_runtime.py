"""Select an explicitly installed engine; never call CPU execution Vulkan."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def selected_engine():
    path = ROOT / ".build/whisper/ready.json"
    if os.environ.get("SINGLAYER_ENGINE", "auto") != "crisper" and path.is_file():
        config = json.loads(path.read_text())
        if (config.get("backend") != "whisper.cpp" or config.get("device") != "vulkan"
                or config.get("model") != "large-v3-turbo-q5_0"):
            raise ValueError("Motor Whisper no validado")
        if not all(Path(config[key]).is_file() for key in ("binary", "model_path")):
            raise ValueError("Falta el motor Whisper instalado")
        return {**config, "label": "Whisper.cpp · Vulkan"}
    return {"backend": "crisperwhisper", "device": "cpu", "label": "CrisperWhisper · CPU",
            "ready": (ROOT / ".build/crisperwhisper/ready.json").is_file()}
