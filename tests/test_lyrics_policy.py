import pytest

from singlayer.lyrics_policy import lyric_policy


@pytest.mark.parametrize("title", ["Song (sped up)", "Song 1.25x", "Song slowed", "Cutting Crew", "Sloop Song"])
def test_speed_changes_keep_catalog_acoustic_alignment(title):
    assert lyric_policy({"title": title}) == {"route": "alignment", "engine": "auto"}


@pytest.mark.parametrize("title", ["Song (Remix)", "Song MASHUP", "Song bootleg", "Song looped", "Song - best part"])
def test_structural_edits_use_whisper_actual_words(title):
    assert lyric_policy({"title": title}, engine="crisper") == {"route": "transcript", "engine": "whisper"}


def test_explicit_user_source_and_engine_remain_available():
    assert lyric_policy({"title": "Song Remix"}, "transcript", "crisper") == {"route": "transcript", "engine": "crisper"}
    assert lyric_policy({"title": "Song Remix"}, "catalog", "crisper") == {"route": "catalog", "engine": "crisper"}
