"""Bounded recognition/lyrics orchestration, independent of Qt and desktop audio."""

import asyncio
import re
import unicodedata
from difflib import SequenceMatcher

NATIVE = ("lrclib", "netease", "kugou")
EXTRA = ("Musixmatch", "Megalobiz")
EDIT = re.compile(r"\b(?:slowed(?:[ _-]*down)?|spe(?:d|ed)[ _-]*up|nightcore|daycore|reverb(?:ed)?|pitched|muffled|bass[ _-]*boost(?:ed)?|8d(?:[ _-]*audio)?|tiktok[ _-]*(?:version|edit)|remix|mashup|looped|snippet|edit(?:[ _-]*audio)?|\d+(?:\.\d+)?x)\b", re.I)
EDIT_WORDS = {"slowed", "down", "sped", "speed", "up", "nightcore", "daycore", "reverb", "reverbed",
              "pitched", "remix", "mashup", "looped", "snippet", "edit", "audio", "extra", "and", "muffled",
              "bass", "boost", "boosted", "8d", "tiktok", "version", "to", "perfection"}
SEPARATOR = r"\s+(?:[-–—|]|//)\s+"


def edit_suffix(value):
    tokens = re.findall(r"\w+", value.casefold())
    return bool(EDIT.search(value) and tokens and all(
        word in EDIT_WORDS or re.fullmatch(r"\d+(?:x|db)?", word) for word in tokens
    ))


def catalog_text(value):
    from kotonoha.lyrics.title_grammar import base_title

    value = clean_search_text(value)
    value = re.sub(r"[([{]([^()\[\]{}]*)[)\]}]",
                   lambda m: "" if EDIT.search(m.group(1)) else m.group(0), value)
    # Unbracketed editing suffixes are common on SoundCloud.
    marker = EDIT.search(value)
    if marker and marker.start() > 0 and edit_suffix(value[marker.start():]):
        value = value[:marker.start()].rstrip(" -_+,&|/")
    return base_title(value).strip(" -_+,&|/")



def clean_search_text(value):
    """Normalize decorative Unicode, not arbitrary words that might be a title."""
    value = unicodedata.normalize("NFKC", value)
    value = re.sub(r"\.(?:mp3|wav|flac)$", "", value, flags=re.I)
    value = re.sub(r"[^\w\s'’()\[\]{}&+.,:–—|/-]", " ", value)
    return " ".join(value.split()).strip(" -–—")


def identity_key(candidate):
    def key(value):
        value = unicodedata.normalize("NFKD", value.casefold())
        return " ".join("".join(c for c in value if not unicodedata.combining(c)).split())

    return key(candidate["title"]), key(candidate.get("artist", ""))


def same_recording(a, b):
    # Prefer Shazam's recording id. Text similarity is only a fallback for
    # recognition results, never proof that an uploader's metadata is correct.
    if a.get("recording_id") and b.get("recording_id"):
        return a["recording_id"] == b["recording_id"]
    at, aa = identity_key(a)
    bt, ba = identity_key(b)
    return bool(
        aa
        and ba
        and SequenceMatcher(None, at, bt).ratio() >= 0.94
        and SequenceMatcher(None, aa, ba).ratio() >= 0.94
    )


def search_candidates(track):
    primary = search_identity(track)
    candidates = [primary]
    if track.get("manual"):
        return candidates
    cleaned = {
        **track,
        "title": clean_search_text(track["title"]),
        "artist": clean_search_text(track.get("artist", "")),
    }
    candidates.append(search_identity(cleaned))

    split = re.split(SEPARATOR, cleaned["title"], maxsplit=1)
    if len(split) == 2 and not edit_suffix(split[1]) and (primary["edited"] or track.get("source") == "SoundCloud"):
        candidates.append({"title": catalog_text(split[0]), "artist": catalog_text(split[1]), "duration": None})
    # Uploader names are not reliable artist identifiers. Title-only fallback
    # remains explicitly unverified if audio cannot establish identity.
    if track.get("source") == "SoundCloud":
        candidates.append({"title": primary["title"], "artist": "", "duration": None})
    seen, unique = set(), []
    for candidate in candidates:
        key = identity_key(candidate)
        if key not in seen and candidate["title"]:
            seen.add(key)
            unique.append(candidate)
    return unique[:4]


def search_identity(track):
    """Keep raw identity elsewhere; this is explicitly a search interpretation."""
    from kotonoha.lyrics.title_grammar import base_title

    title, artist = clean_search_text(track["title"]), clean_search_text(track.get("artist", ""))
    edited = bool(EDIT.search(title))
    # Uploader != performer is common on SoundCloud. Keep the raw title in the UI.
    split = re.split(SEPARATOR, title, maxsplit=1)
    if (
        len(split) == 2
        and not track.get("manual")
        and (edited or not artist or track.get("source") == "SoundCloud")
    ):
        if edit_suffix(split[1]):
            title = split[0]
        else:
            artist, title = split
    title = catalog_text(title) if not track.get("manual") else base_title(title)
    artist = catalog_text(artist) if not track.get("manual") else artist
    return {
        "title": title,
        "artist": artist,
        "duration": None if edited else track.get("duration"),
        "edited": edited,
    }


async def resolve(track, invoke, emit, *, recognize=False, audio_allowed=False):
    """Each invoke is an isolated cancellable operation; never launch unbounded retries."""
    identity = search_identity(track)
    candidates = search_candidates(track)
    uncertain = identity["edited"] or not identity["artist"] or track.get("source") == "SoundCloud"
    emit({"stage": "metadata", "state": "done", "detail": f"{identity['title']} · {identity['artist']}"})
    if identity["edited"]:
        emit({"stage": "timing", "state": "warning", "detail": "Versión editada: ajusta desfase y velocidad"})
    lookups = {}
    recognition_result = {}
    slots = asyncio.Semaphore(4)

    async def limited(action, payload, timeout):
        async with slots:
            return await invoke(action, payload, timeout)

    async def lookup(candidate):
        query_key = identity_key(candidate)
        if query_key not in lookups:
            lookups[query_key] = asyncio.create_task(lookup_once(candidate))
        return await asyncio.shield(lookups[query_key])

    async def lookup_once(candidate):
        # Native providers first; two extra catalogs only if all three miss.
        for providers in (NATIVE, EXTRA):

            async def one(provider):
                emit({"stage": provider, "state": "running", "detail": "Buscando letras"})
                try:
                    result = await limited("provider", {"provider": provider, **candidate}, 22)
                    state = (
                        "done" if result.get("document") else "missing" if result.get("missing") else "empty"
                    )
                    emit(
                        {
                            "stage": provider,
                            "state": state,
                            "detail": result.get(
                                "error", "Con letras" if state == "done" else "Sin coincidencia"
                            ),
                        }
                    )
                    return result if result.get("document") else None
                except Exception as error:
                    emit({"stage": provider, "state": "error", "detail": str(error)[:180]})
                    return None

            tasks = [asyncio.create_task(one(provider)) for provider in providers]
            try:
                for completed in asyncio.as_completed(tasks):
                    result = await completed
                    if result:
                        return result
            finally:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
        return None

    async def audio_lookup():
        nonlocal identity, recognition_result
        votes = []
        best = None
        for attempt in range(1, 4):
            stage = f"shazam-{attempt}"
            emit({"stage": stage, "state": "running", "detail": f"Escuchando fragmento {attempt}/3 · 12 s"})
            try:
                identified = await limited("recognize", {"title": track["title"]}, 45)
            except Exception as error:
                emit({"stage": stage, "state": "error", "detail": str(error)[:180]})
                break  # Capture/transport failures aren't 'no match'.
            if identified.get("missing"):
                emit({"stage": stage, "state": "missing", "detail": identified["error"]})
                break
            if not identified.get("title"):
                emit({"stage": stage, "state": "empty", "detail": "Sin reconocimiento"})
                continue
            emit(
                {"stage": stage, "state": "done", "detail": f"{identified['title']} · {identified['artist']}"}
            )
            votes.append(identified)
            group = max(
                ([v for v in votes if v is candidate or same_recording(v, candidate)] for candidate in votes),
                key=len,
            )
            best = group[0]
            emit(
                {
                    "stage": "consensus",
                    "state": "done" if len(group) >= 2 else "running",
                    "detail": f"{len(group)} de {attempt} muestras coinciden · {best['title']}",
                }
            )
            if len(group) >= 2:
                identity = {**best, "duration": None}
                recognition_result = {
                    "recognized": best,
                    "evidence": {"matches": len(group), "samples": attempt,
                                 "confirmed": False, "recognition_confirmed": True},
                }
                result = await lookup(identity)
                if result:
                    return {
                        **result,
                        "recognized": best,
                        "evidence": {"matches": len(group), "samples": attempt, "confirmed": True},
                    }
                # Shazam may identify a separately released slowed/remix recording.
                # Its artist and duration cannot establish the original lyrics.
                normalized = search_identity(best)
                if normalized["edited"]:
                    for candidate in (normalized, {**normalized, "artist": ""}):
                        result = await lookup(candidate)
                        if result:
                            return {**result, **recognition_result,
                                    "candidates": [result["document"]]}
        # One hit is not corroboration; preserve as a labelled fallback only.
        if best and len(votes) == 1:
            identity = {**best, "duration": None}
            result = await lookup(identity)
            if result:
                return {
                    **result,
                    "recognized": best,
                    "evidence": {"matches": 1, "samples": attempt, "confirmed": False},
                }
        return None

    async def metadata_lookup():
        found = []
        for index, candidate in enumerate(candidates, 1):
            emit(
                {
                    "stage": "metadata-alternative",
                    "state": "running",
                    "detail": f"Buscando variante {index}/{len(candidates)} · {candidate['title']}",
                }
            )
            result = await lookup(candidate)
            if result:
                found.append(result["document"])
                if track.get("source") != "SoundCloud" or len(found) >= 2:
                    break
        if found:
            return {"document": found[0], "candidates": found,
                    "evidence": {"confirmed": False, "strategy": "metadata"}}
        return None

    paths = []
    if not recognize:
        paths.append(asyncio.create_task(metadata_lookup()))
    if audio_allowed:
        paths.append(asyncio.create_task(audio_lookup()))
    else:
        emit(
            {
                "stage": "shazam",
                "state": "skipped",
                "detail": "Reconocimiento disponible durante la reproducción",
            }
        )
    try:
        fallback = None
        for completed in asyncio.as_completed(paths):
            result = await completed
            if result:
                if uncertain and audio_allowed and not result.get("evidence", {}).get("confirmed"):
                    fallback = result
                    emit(
                        {
                            "stage": "verification",
                            "state": "running",
                            "detail": "Letra candidata encontrada · contrastando audio",
                        }
                    )
                    continue
                return result
        if fallback:
            if recognition_result:
                fallback = {**fallback, "recognized": recognition_result["recognized"],
                            "evidence": {**fallback.get("evidence", {}),
                                         "recognition_confirmed": True}}
            return fallback
    finally:
        for task in [*paths, *lookups.values()]:
            if not task.done():
                task.cancel()
        await asyncio.gather(*paths, *lookups.values(), return_exceptions=True)
    # Text-only fallback is labelled honestly and never assigned invented timestamps.
    emit({"stage": "Genius", "state": "running", "detail": "Buscando texto sin sincronizar"})
    try:
        result = await invoke("provider", {"provider": "Genius", **identity}, 22)
        emit(
            {
                "stage": "Genius",
                "state": "done" if result.get("plain") else "empty",
                "detail": "Texto sin tiempos"
                if result.get("plain")
                else result.get("error", "Sin coincidencia"),
            }
        )
        return {**recognition_result, **result} if result.get("plain") else recognition_result
    except Exception as error:
        emit({"stage": "Genius", "state": "error", "detail": str(error)[:180]})
        return recognition_result
