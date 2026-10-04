"""Choose lyric authority without confusing recording identity with timing."""
import re
import unicodedata

STRUCTURAL_EDIT = re.compile(
    r"\b(?:remix|mashup|bootleg|medley|loop(?:ed)?|cut|snippet|excerpt)\b|\bbest\s+part\b",
    re.I,
)


def lyric_policy(track, source="auto", engine="auto"):
    title = unicodedata.normalize("NFKC", (track or {}).get("title", ""))
    if source == "catalog":
        return {"route": "catalog", "engine": engine}
    if source == "transcript":
        return {"route": "transcript", "engine": engine}
    if STRUCTURAL_EDIT.search(title):
        return {"route": "transcript", "engine": "whisper"}
    return {"route": "alignment", "engine": engine}
