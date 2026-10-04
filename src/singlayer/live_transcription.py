"""Bounded browser-only rolling transcription, owned by one cancellable worker."""

import asyncio
import io
import json
import math
import time
import wave
from array import array

import aiohttp

from .browser_audio import capture_command
from .transcription import transcribe_window

RATE = 16000
WINDOW = 12
HOP = 8


class PlaybackChanged(Exception):
    """Discard this epoch; the panel may start a fresh capture."""


def continuous(previous, current, elapsed):
    if not current or not current.get("playing") or current.get("stale"):
        return False
    if current.get("id") != previous.get("id"):
        return False
    position = current.get("position", -1)
    return math.isfinite(position) and abs(position - previous["position"] - elapsed) < 1.5


def wav_window(pcm):
    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(RATE)
        wav.writeframes(pcm)
    return out.getvalue()


def audible(pcm):
    samples = array("h", pcm)
    return bool(samples) and sum(s * s for s in samples) / len(samples) > 80**2


def merge_transcript(previous, incoming):
    """Overlap is replaced by the newest window, retaining only bounded history."""
    if not incoming:
        return previous
    boundary = incoming["lines"][0]["start"]
    end = incoming["lines"][-1]["end"]
    retained = [dict(line) for line in (previous or {}).get("lines", [])
                if line["end"] <= boundary or line["start"] >= end]
    candidates = sorted([*retained, *incoming["lines"]], key=lambda line: line["start"])
    lines = []
    for line in candidates:
        if lines and not line.get("words") and not lines[-1].get("words") and lines[-1]["text"].casefold() == line["text"].casefold() and line["start"] - lines[-1]["end"] < 2:
            lines[-1]["end"] = line["end"]
        else:
            lines.append(dict(line))
    lines = lines[-512:]
    for index, line in enumerate(lines):
        line["index"] = index
        line["id"] = f"live-{index}-{line['start']:.3f}"
    return {**incoming, "lines": lines}


async def run_live(data, emit):
    try:
        await _run_live(data, emit)
    except PlaybackChanged:
        emit({"discontinuity": True})


async def _run_live(data, emit):
    # Local import avoids a worker-module import cycle.
    from .worker import audio_target

    expected = data["track"]["id"]
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=2)) as session:
        async def status():
            async with session.get("http://127.0.0.1:8975/status", allow_redirects=False) as response:
                response.raise_for_status()
                payload = json.loads(await response.content.read(262144))
                track = payload.get("track")
                if payload.get("service") != "singlayer" or not track or track.get("id") != expected:
                    raise PlaybackChanged()
                return track

        for _ in range(60):
            try:
                async with session.get("http://127.0.0.1:28748/health", allow_redirects=False) as response:
                    if response.status == 200:
                        health = json.loads(await response.content.read(4096))
                        if health.get("service") == "singlayer-transcription" and health.get("ready") is True and not health.get("busy", False):
                            break
            except (aiohttp.ClientError, TimeoutError):
                pass
            await asyncio.sleep(.5)
        else:
            raise RuntimeError("El motor de transcripción no está preparado; revisa el modelo y el diagnóstico")
        window, hop = (24, 16) if health.get("backend") == "whisper.cpp" else (WINDOW, HOP)
        track = await status()
        if not continuous(track, track, 0):
            raise PlaybackChanged()
        target = await audio_target(track["title"])
        if not target:
            raise RuntimeError("No se puede aislar el audio del navegador")
        anchor = await status()
        started = time.monotonic()
        process = await asyncio.create_subprocess_exec(
            *capture_command(target), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
        )
        pending = asyncio.Queue(maxsize=1)

        async def capture():
            buffer = bytearray()
            samples = 0
            while True:
                chunk = await asyncio.wait_for(process.stdout.readexactly(RATE * 2), 3)
                buffer.extend(chunk)
                samples += RATE
                if len(buffer) >= window * RATE * 2:
                    pcm = bytes(buffer[:window * RATE * 2])
                    begin = anchor["position"] + samples / RATE - window
                    if pending.full():
                        pending.get_nowait()
                        emit({"live_status": "Transcripción retrasada · descartando ventana antigua"})
                    pending.put_nowait((pcm, begin))
                    del buffer[:hop * RATE * 2]

        async def monitor():
            previous, observed = anchor, started
            checks = 0
            while True:
                await asyncio.sleep(.4)
                current = await status()
                now = time.monotonic()
                if not continuous(previous, current, now - observed):
                    raise PlaybackChanged()
                # Detect clock drift accumulated during capture, not just one poll.
                if abs(current["position"] - anchor["position"] - (now - started)) > 1.5:
                    raise PlaybackChanged()
                previous, observed = current, now
                checks += 1
                if checks % 5 == 0 and await audio_target(current["title"]) != target:
                    raise PlaybackChanged()

        async def infer():
            while True:
                pcm, begin = await pending.get()
                if not audible(pcm):
                    emit({"live_status": "Esperando voz · audio en silencio"})
                    continue
                try:
                    document = await transcribe_window(wav_window(pcm), begin)
                except ValueError:
                    # Model timestamps can exceed the captured audio on music.
                    # Keep the transport strict; discard this window and recover.
                    emit({"live_status": "Fragmento incierto descartado · esperando el siguiente"})
                    continue
                current = await status()
                if not continuous(anchor, current, time.monotonic() - started):
                    raise PlaybackChanged()
                if document:
                    emit({"transcript": document, "lag": max(0, current["position"] - document["lines"][-1]["end"])})
                else:
                    emit({"live_status": "Sin palabras fiables · esperando otro fragmento"})

        tasks = [asyncio.create_task(task()) for task in (capture, monitor, infer)]
        try:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
            for task in done:
                task.result()
        except PlaybackChanged:
            emit({"discontinuity": True})
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), 2)
                except TimeoutError:
                    process.kill()
                    await process.wait()
