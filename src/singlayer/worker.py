"""Reuse upstream engines in short-lived processes; stdout is a JSONL event stream."""

import asyncio
import importlib.util
import io
import json
import shutil
import signal
import sys
import tempfile
import wave
from dataclasses import asdict
from pathlib import Path

from .browser_audio import capture_args, select_stream
from .diagnostics import record
from .workflow import resolve


def emit(event):
    print(json.dumps(event, ensure_ascii=False), flush=True)


async def command(argv, *, data=None, timeout=22, limit=4_000_000):
    """Drain bounded output and always reap children on timeout/cancellation."""
    process = await asyncio.create_subprocess_exec(
        *argv,
        stdin=asyncio.subprocess.PIPE if data else asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )

    async def read():
        if data:
            process.stdin.write(data)
            await process.stdin.drain()
            process.stdin.close()
        output = bytearray()
        while chunk := await process.stdout.read(65536):
            output.extend(chunk)
            if len(output) > limit:
                raise ValueError("Respuesta demasiado grande")
        code = await process.wait()
        if code:
            raise RuntimeError(f"Proceso falló ({code}): {Path(argv[0]).name}")
        return bytes(output)

    try:
        return await asyncio.wait_for(read(), timeout)
    finally:
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), 2)
            except TimeoutError:
                process.kill()
                await process.wait()


def document(lines, provider, title, artist):
    from kotonoha.lyrics.models import LyricsDocument, TimingKind, validate_document

    timed = tuple(lines)
    if not timed or len(timed) > 4096:
        return None
    timing = TimingKind.WORD if any(line.has_word_timing for line in timed) else TimingKind.LINE
    validate_document(LyricsDocument(source_id=provider, timing=timing, lines=timed))
    return {
        "source": provider,
        "sourceName": provider,
        "title": title,
        "artist": artist,
        "timing": timing.value,
        "lines": [asdict(line) for line in timed],
    }


async def provider_search(data):
    provider = data["provider"]
    if provider in {"lrclib", "netease", "kugou"}:
        import aiohttp
        from kotonoha.lyrics import kugou, lrclib, netease
        from kotonoha.lyrics.match import TrackMetadata

        module = {"lrclib": lrclib, "netease": netease, "kugou": kugou}[provider]
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=18)) as session:
            artifact = await module.fetch_artifact(
                session,
                TrackMetadata(data["title"], data.get("artist", ""), duration_s=data.get("duration")),
                fuzzy=True,
            )
        if not artifact:
            return {}
        return {"document": document(artifact.lines, provider, artifact.title, artifact.artist)}
    if provider not in {"Musixmatch", "Megalobiz", "Genius"}:
        raise ValueError("Proveedor desconocido")
    if importlib.util.find_spec("syncedlyrics") is None:
        return {"missing": True, "error": "Instala los motores adicionales"}
    import syncedlyrics
    from kotonoha.lyrics.lrc_parser import parse_lrc

    result = syncedlyrics.search(
        f"{data['title']} {data.get('artist', '')}",
        providers=[provider],
        synced_only=provider != "Genius",
        plain_only=provider == "Genius",
        enhanced=provider == "Musixmatch",
    )
    if not result:
        return {}
    if len(result.encode()) > 1_000_000:
        raise ValueError("Letra demasiado grande")
    if provider == "Genius":
        return {"plain": result, "source": provider}
    return {"document": document(parse_lrc(result), provider, data["title"], data.get("artist", ""))}


async def alternatives(data):
    import re

    import aiohttp
    from kotonoha.lyrics.lrclib import search_artifacts
    from kotonoha.lyrics.match import TrackMetadata
    from kotonoha.lyrics.title_grammar import base_title

    from .workflow import search_identity

    track = data["track"]
    identity = search_identity(track)
    titles = [identity["title"]]
    if track.get("source") == "SoundCloud":
        titles += [base_title(part) for part in re.split(r"\s+[-–—]\s+", track["title"], maxsplit=1)]
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=18)) as session:
        results = await asyncio.gather(
            *(search_artifacts(session, TrackMetadata(title, "")) for title in dict.fromkeys(titles)),
            return_exceptions=True,
        )
    documents = []
    for result in results:
        if isinstance(result, BaseException):
            continue
        for artifact in result:
            doc = document(artifact.lines, "lrclib", artifact.title, artifact.artist)
            if doc and doc not in documents:
                documents.append(doc)
    return {"documents": documents[:20], "failed": all(isinstance(r, BaseException) for r in results)}


async def audio_target(title=""):
    inputs, sinks = await asyncio.gather(
        command(["pactl", "-f", "json", "list", "sink-inputs"], timeout=3),
        command(["pactl", "-f", "json", "list", "sinks"], timeout=3),
    )
    return select_stream(json.loads(inputs), json.loads(sinks), title)


async def browser_sample(target):
    process = await asyncio.create_subprocess_exec(
        "parec",
        *capture_args(target),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        pcm = await asyncio.wait_for(process.stdout.readexactly(12 * 16000 * 2), 17)
    finally:
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), 2)
            except TimeoutError:
                process.kill()
                await process.wait()
    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(pcm)
    return out.getvalue()


async def recognize(data=None):
    songrec = shutil.which("songrec")
    root = Path(__file__).resolve().parents[2]
    isolated = root / ".build/recognizer/bin/python"
    python = str(isolated) if isolated.is_file() else sys.executable
    if not songrec and not isolated.is_file() and importlib.util.find_spec("shazamio") is None:
        return {"missing": True, "error": "Falta SongRec o ShazamIO. Instala los motores."}
    if not songrec:
        # Native modules can crash the interpreter despite find_spec succeeding.
        # Probe in isolation before recording any audio.
        try:
            await command([python, "-c", "from shazamio import Shazam"], timeout=10)
        except (RuntimeError, TimeoutError):
            return {
                "missing": True,
                "error": "ShazamIO no puede iniciarse con este Python. Instala SongRec o un motor compatible.",
            }
    target = await audio_target((data or {}).get("title", ""))
    if not target:
        return {"missing": True, "error": "No se puede aislar el audio del navegador"}
    audio = await browser_sample(target)
    if songrec:
        with tempfile.TemporaryDirectory(prefix="singlayer-recognition-") as directory:
            path = Path(directory) / "sample.wav"
            path.write_bytes(audio)
            raw = await command([songrec, "audio-file-to-recognized-song", str(path)], timeout=22)
            result = json.loads(raw)
    else:
        raw = await command([python, str(root / "scripts/recognize_audio.py")], data=audio, timeout=25)
        result = json.loads(raw)
    if result.get("fatal"):
        raise RuntimeError(result["fatal"])
    track = result.get("track") or {}
    # Match offsets/skews are not treated as a reliable karaoke clock.
    return {
        "title": track.get("title", ""),
        "artist": track.get("subtitle", ""),
        "recording_id": str(track.get("key", "")),
    }


async def invoke(action, data, timeout):
    raw = await command(
        [sys.executable, "-m", "singlayer.worker", action], data=json.dumps(data).encode(), timeout=timeout
    )
    result = json.loads(raw)
    if result.get("fatal"):
        raise RuntimeError(result["fatal"])
    return result


async def main_async(action, data):
    if action == "live":
        from .live_transcription import run_live

        await run_live(data, emit)
    elif action == "provider":
        emit(await provider_search(data))
    elif action == "recognize":
        emit(await recognize(data))
    elif action == "audio-target":
        emit({"target": await audio_target(data.get("title", ""))})
    elif action == "pronunciation":
        from .pronunciation import generate

        emit(await generate(data["document"]))
    elif action == "alternatives":
        emit(await alternatives(data))
    elif action == "resolve":
        result = await resolve(
            data["track"],
            invoke,
            emit,
            recognize=data.get("recognize", False),
            audio_allowed=data.get("audio_allowed", False),
        )
        emit({"result": result, "finished": True})
    else:
        raise ValueError("Acción desconocida")


def main():
    data = json.loads(sys.stdin.buffer.read(262144))

    async def run():
        task = asyncio.current_task()
        asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, task.cancel)
        await main_async(sys.argv[1], data)

    try:
        asyncio.run(run())
    except asyncio.CancelledError:
        pass
    except TimeoutError:
        record(sys.argv[1], "TimeoutError")
        emit({"fatal": "Tiempo de espera agotado: el servicio no respondió. Revisa la conexión y reintenta."})
    except Exception as error:
        record(sys.argv[1], type(error).__name__, status=getattr(error, "status", None))
        emit({"fatal": f"{type(error).__name__}: {error}"[:500]})


if __name__ == "__main__":
    main()
