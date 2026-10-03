"""Bounded recognition/lyrics orchestration, independent of Qt and desktop audio."""

import asyncio
import re

NATIVE = ("lrclib", "netease", "kugou")
EXTRA = ("Musixmatch", "Megalobiz")


def search_identity(track):
    """Keep raw identity elsewhere; this is explicitly a search interpretation."""
    from kotonoha.lyrics.title_grammar import base_title

    title, artist = track["title"], track.get("artist", "")
    edited = bool(re.search(r"slowed|sped[ -]?up|remix|nightcore|snippet|edit audio", title, re.I))
    # Uploader != performer is common on SoundCloud. Keep the raw title in the UI.
    split = re.split(r"\s+[-–—]\s+", title, maxsplit=1)
    if (
        len(split) == 2
        and not track.get("manual")
        and (edited or not artist or track.get("source") == "SoundCloud")
    ):
        artist, title = split
    title = base_title(title)
    return {
        "title": title,
        "artist": artist,
        "duration": None if edited else track.get("duration"),
        "edited": edited,
    }


async def resolve(track, invoke, emit, *, recognize=False, audio_allowed=False):
    """Each invoke is an isolated cancellable operation; never launch unbounded retries."""
    identity = search_identity(track)
    emit({"stage": "metadata", "state": "done", "detail": f"{identity['title']} · {identity['artist']}"})
    if identity["edited"]:
        emit({"stage": "timing", "state": "warning", "detail": "Versión editada: ajusta desfase y velocidad"})
    lookups = {}
    slots = asyncio.Semaphore(4)

    async def limited(action, payload, timeout):
        async with slots:
            return await invoke(action, payload, timeout)

    async def lookup(candidate):
        query_key = (candidate["title"].casefold(), candidate["artist"].casefold())
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
        nonlocal identity
        for attempt in range(1, 4):
            stage = f"shazam-{attempt}"
            emit({"stage": stage, "state": "running", "detail": f"Escuchando fragmento {attempt}/3 · 12 s"})
            try:
                identified = await limited("recognize", {}, 45)
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
            identity = {**identified, "duration": None}
            result = await lookup(identity)
            if result:
                return {**result, "recognized": identified}
        return None

    paths = []
    if not recognize:
        paths.append(asyncio.create_task(lookup(identity)))
    if audio_allowed:
        paths.append(asyncio.create_task(audio_lookup()))
    else:
        emit(
            {
                "stage": "shazam",
                "state": "skipped",
                "detail": "Activa Audio del sistema para permitir reconocimiento",
            }
        )
    try:
        for completed in asyncio.as_completed(paths):
            result = await completed
            if result:
                return result
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
        return result if result.get("plain") else {}
    except Exception as error:
        emit({"stage": "Genius", "state": "error", "detail": str(error)[:180]})
        return {}
