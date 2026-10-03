"""Reuse upstream engines in short-lived processes; stdout is a JSONL event stream."""

import asyncio
import importlib.util
import json
import shutil
import signal
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

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


async def recognize():
    songrec = shutil.which("songrec")
    if not songrec and importlib.util.find_spec("shazamio") is None:
        return {"missing": True, "error": "Falta SongRec o ShazamIO. Instala los motores."}
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return {"missing": True, "error": "Falta FFmpeg para capturar la salida de audio"}
    # Explicit monitor input: never default to a microphone. No audio is retained.
    audio = await command(
        [
            ffmpeg,
            "-nostdin",
            "-v",
            "error",
            "-f",
            "pulse",
            "-i",
            "@DEFAULT_MONITOR@",
            "-t",
            "12",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-f",
            "wav",
            "pipe:1",
        ],
        timeout=17,
        limit=600_000,
    )
    if songrec:
        with tempfile.TemporaryDirectory(prefix="singlayer-recognition-") as directory:
            path = Path(directory) / "sample.wav"
            path.write_bytes(audio)
            raw = await command([songrec, "audio-file-to-recognized-song", str(path)], timeout=22)
            result = json.loads(raw)
    else:
        from shazamio import Shazam

        async with Shazam() as shazam:
            result = await asyncio.wait_for(shazam.recognize(audio), 22)
    track = result.get("track") or {}
    # Match offsets/skews are not treated as a reliable karaoke clock.
    return {"title": track.get("title", ""), "artist": track.get("subtitle", "")}


async def invoke(action, data, timeout):
    raw = await command(
        [sys.executable, "-m", "singlayer.worker", action], data=json.dumps(data).encode(), timeout=timeout
    )
    result = json.loads(raw)
    if result.get("fatal"):
        raise RuntimeError(result["fatal"])
    return result


async def main_async(action, data):
    if action == "provider":
        emit(await provider_search(data))
    elif action == "recognize":
        emit(await recognize())
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
    data = json.loads(sys.stdin.buffer.read(65536))

    async def run():
        task = asyncio.current_task()
        asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, task.cancel)
        await main_async(sys.argv[1], data)

    try:
        asyncio.run(run())
    except asyncio.CancelledError:
        pass
    except Exception as error:
        emit({"fatal": f"{type(error).__name__}: {error}"[:500]})


if __name__ == "__main__":
    main()
