import json

import pytest

from singlayer.crisper_model import restore_runtime_config


def test_conversion_restores_native_language_suppression_and_alignment(tmp_path):
    (tmp_path / "config.json").write_text(json.dumps({"num_mel_bins": 80, "vocab_size": 51896}))
    generation = {"lang_to_id": {"<|ja|>": 50266, "<|en|>": 50259},
                  "suppress_tokens": [-1, 123], "begin_suppress_tokens": [220],
                  "alignment_heads": [[1, 2], [3, 4]]}
    (tmp_path / "generation_config.json").write_text(json.dumps(generation))
    restore_runtime_config(tmp_path)
    config = json.loads((tmp_path / "config.json").read_text())
    assert config["lang_ids"] == [50259, 50266]
    assert config["suppress_ids"] == [123]
    assert config["suppress_ids_begin"] == [220]
    assert config["alignment_heads"] == generation["alignment_heads"]
    assert config["num_mel_bins"] == 80


@pytest.mark.parametrize("languages", [{}, {"<|en|>": True}, {"<|en|>": -1}])
def test_invalid_native_language_metadata_is_rejected(tmp_path, languages):
    original = '{"num_mel_bins": 80}'
    (tmp_path / "config.json").write_text(original)
    (tmp_path / "generation_config.json").write_text(json.dumps({"lang_to_id": languages}))
    with pytest.raises(ValueError):
        restore_runtime_config(tmp_path)
    assert (tmp_path / "config.json").read_text() == original
