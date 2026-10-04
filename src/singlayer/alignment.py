"""Two measured anchors correct constant speed and offset, not arbitrary edits."""

import math


def calibrate(first, second):
    """Anchors are (browser seconds, original lyric seconds)."""
    p1, l1 = first
    p2, l2 = second
    if not all(math.isfinite(v) and v >= 0 for v in (p1, l1, p2, l2)):
        raise ValueError("Referencias temporales inválidas")
    if p2 - p1 < 15 or l2 <= l1:
        raise ValueError("Marca otra línea posterior al menos 15 segundos después")
    speed = (l2 - l1) / (p2 - p1)
    offset = l1 - p1 * speed
    if not 0.5 <= speed <= 2 or abs(offset) > 3600:
        raise ValueError("Referencias incompatibles; vuelve a marcarlas")
    return offset, speed


def unique_match(text, lines):
    """Match one ASR phrase to 1–3 catalog lines; repeated choruses are ambiguous."""
    import re
    import unicodedata
    from difflib import SequenceMatcher

    def words(value):
        value = unicodedata.normalize("NFKC", value).casefold()
        # Decoration must not split words or distinguish typographic apostrophes.
        value = "".join(char for char in value if unicodedata.category(char) != "Cf")
        value = re.sub(r"(?<=\w)['’ʼ](?=\w)", "", value)
        return re.findall(r"[\u3040-\u30ff\u3400-\u9fff]|[^\W\u3040-\u30ff\u3400-\u9fff]+", value)

    query = words(text)
    if len(query) < (8 if any(re.search(r"[\u3040-\u30ff\u3400-\u9fff]", token) for token in query) else 4):
        return None
    scored = []
    for start in range(len(lines)):
        for size in range(1, 4):
            group = lines[start:start + size]
            candidate = words(" ".join(line["text"] for line in group))
            if not candidate:
                continue
            ratio = SequenceMatcher(None, query, candidate, autojunk=False).ratio()
            scored.append((ratio, start, len(group)))
    scored.sort(reverse=True)
    if not scored or scored[0][0] < .82:
        return None
    score, start, size = scored[0]
    # Overlapping candidates refer to the same occurrence, not a second chorus.
    rivals = [item for item in scored[1:] if item[1] + item[2] <= start or item[1] >= start + size]
    if rivals and score - rivals[0][0] < .10:
        return None
    return start, size, score


def contextual_matches(transcript, catalog):
    """Resolve repeats only from two independent phrases in this audio window."""
    segments = transcript["lines"]
    matches = [unique_match(segment["text"], catalog["lines"]) for segment in segments]
    anchors = [(segment["start"], catalog["lines"][match[0]]["start"])
               for segment, match in zip(segments, matches)
               if match and match[1] == 1 and match[2] >= .85]
    anchors.sort()
    if len(anchors) < 2:
        return matches
    try:
        offset, speed = calibrate(anchors[0], anchors[-1])
    except ValueError:
        return matches
    if any(abs((original - offset) / speed - position) > .75 for position, original in anchors):
        return matches
    for index, segment in enumerate(segments):
        if matches[index]:
            continue
        # Never extend a contextual inference beyond the measured unique anchors.
        if not anchors[0][0] <= segment["start"] <= anchors[-1][0]:
            continue
        indices = [i for i, line in enumerate(catalog["lines"])
                   if abs((line["start"] - offset) / speed - segment["start"]) <= 1.5]
        # Only single-line repeats: joining a filtered, noncontiguous catalog
        # would manufacture neighboring phrases that never occurred together.
        if len(indices) == 1:
            found = unique_match(segment["text"], [catalog["lines"][indices[0]]])
            if found and found[1] == 1 and found[2] >= .85:
                matches[index] = (indices[0], 1, found[2])
    return matches


def align_fragment(transcript, catalog):
    """Piecewise mapping only inside observed phrases; never extrapolate across cuts."""
    result = []
    for segment, match in zip(transcript["lines"], contextual_matches(transcript, catalog)):
        if not match:
            continue
        start, size, _ = match
        group = catalog["lines"][start:start + size]
        first = group[0]["start"]
        end = group[-1].get("end")
        if end is None or end <= first:
            continue
        span = segment["end"] - segment["start"]
        speed = (end - first) / span if span > 0 else 0
        if not .5 <= speed <= 2:
            continue
        # Preserve measured CrisperWhisper word boundaries only for an exact
        # single-line match. Fuzzy matches must not borrow another text's words.
        measured = segment.get("words", []) if size == 1 else []
        if measured and " ".join("".join(w["text"] for w in measured).split()).casefold() != " ".join(group[0]["text"].split()).casefold():
            measured = []
        for line in group:
            result.append({
                **line, "start": segment["start"] + (line["start"] - first) / speed,
                "end": segment["start"] + (line["end"] - first) / speed,
                "words": [dict(word) for word in measured], "translation": "",
            })
    if not result:
        return None
    result.sort(key=lambda line: line["start"])
    return {**catalog, "source": "audio-aligned", "sourceName": "Letra alineada al audio · estimada",
            "timing": "Word" if any(line["words"] for line in result) else "Line", "lines": result}


def estimate_clock(transcript, catalog, anchors=None):
    """Three distinct acoustic/text anchors can estimate a constant playback clock.

    This is a prediction, not proof of future sections. A contradictory later
    anchor rejects the entire estimate; repeated choruses alone never qualify.
    Optional anchors retains measured references across overlapping windows.
    """
    if anchors is None:
        anchors = {}
    for segment in (transcript or {}).get("lines", []):
        match = unique_match(segment["text"], catalog["lines"])
        if not match or match[1] != 1 or match[2] < .85:
            continue
        index = match[0]
        original = catalog["lines"][index]["start"]
        point = (segment["start"], original)
        previous = sorted(anchors.values())
        if len(previous) >= 3:
            try:
                old_offset, old_speed = calibrate(previous[0], previous[-1])
                if abs((original - old_offset) / old_speed - point[0]) > .75:
                    anchors.clear()  # Begin measuring the new section after a cut/speed change.
            except ValueError:
                pass
        if index in anchors and abs(anchors[index][0] - point[0]) > .75:
            anchors.clear()  # A changed acoustic occurrence invalidates the old clock.
        anchors[index] = point
    points = sorted(anchors.values())
    if len(points) < 3 or not all(math.isfinite(value) for point in points for value in point):
        return None
    try:
        offset, speed = calibrate(points[0], points[-1])
    except ValueError:
        return None
    if any(abs((original - offset) / speed - position) > .75 for position, original in points):
        return None
    return {"offset": offset, "speed": speed, "anchors": len(points)}
