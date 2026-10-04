"""Restore native CT2 metadata overwritten by CrisperWhisper 2.0.3 conversion."""

import json
from pathlib import Path


def restore_runtime_config(directory):
    directory = Path(directory)
    config = json.loads((directory / "config.json").read_text())
    generation = json.loads((directory / "generation_config.json").read_text())
    languages = generation.get("lang_to_id", {})
    if not languages or any(type(value) is not int or value < 0 for value in languages.values()):
        raise ValueError("Modelo sin identificadores de idioma válidos")
    config["lang_ids"] = sorted(set(languages.values()))
    for source, target in (("suppress_tokens", "suppress_ids"),
                           ("begin_suppress_tokens", "suppress_ids_begin")):
        values = generation.get(source, [])
        if not isinstance(values, list) or any(type(value) is not int for value in values):
            raise ValueError("Modelo sin configuración de supresión válida")
        config[target] = [value for value in values if value >= 0]
    if "alignment_heads" in generation:
        config["alignment_heads"] = generation["alignment_heads"]
    temporary = directory / "config.json.part"
    temporary.write_text(json.dumps(config, indent=2))
    temporary.replace(directory / "config.json")
