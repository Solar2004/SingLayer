"""Analyze one exact public upload; bounded download, local audio, full clock."""
import asyncio
import hashlib
import io
import json
import math
import os
import re
import shutil
import signal
import tempfile
import time
import unicodedata
import wave
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlsplit

import aiohttp

from .alignment import unique_match
from .live_transcription import merge_transcript
from .transcription import transcribe_window

MAX_DURATION = 900
MAX_BYTES = 100_000_000
FULL_WINDOW = 24
FULL_HOP = 16
SITES = ("youtube.com", "youtu.be", "soundcloud.com", "bandcamp.com", "vimeo.com", "mixcloud.com",
         "dailymotion.com", "audiomack.com")


def valid_url(value):
    parsed = urlsplit(value.strip())
    host = (parsed.hostname or "").lower()
    if (parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443)
            or not any(host == domain or host.endswith("." + domain) for domain in SITES)):
        raise ValueError("Usa un enlace HTTPS de SoundCloud, YouTube u otro sitio musical admitido")
    return value.strip()


def recording_matches(info, track):
    duration = info.get("duration")
    if (not isinstance(duration, (int, float)) or not math.isfinite(duration)
            or not 0 < duration <= MAX_DURATION or info.get("is_live") or info.get("entries") is not None):
        raise ValueError("Se requiere una pista individual de hasta 15 minutos, sin emisión en directo")
    expected = (track or {}).get("duration", 0)
    if expected and abs(duration - expected) > max(2, expected * .02):
        raise ValueError("La duración del enlace no coincide con la pista del navegador")
    if track:
        def title(value):
            return " ".join(re.findall(r"\w+", unicodedata.normalize("NFKC", value).casefold()))
        if SequenceMatcher(None, title(info.get("title", "")), title(track["title"])).ratio() < .8:
            raise ValueError("El título del enlace no coincide con la pista del navegador")
    return duration


async def run_command(argv, *, timeout, data=None, limit=4_000_000, directory=None):
    """Reap the owned process group, including downloader/ffmpeg children."""
    process = await asyncio.create_subprocess_exec(
        *argv, start_new_session=True, stdin=asyncio.subprocess.PIPE if data else asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
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
                raise ValueError("Salida del analizador demasiado grande")
        if await process.wait():
            raise RuntimeError(f"{Path(argv[0]).name} no pudo obtener la pista; puede requerir acceso o estar restringida")
        return bytes(output)
    async def watch_size():
        while True:
            size = 0
            if directory:
                for path in Path(directory).rglob('*'):
                    try:
                        if path.is_file():
                            size += path.stat().st_size
                    except FileNotFoundError:
                        pass  # yt-dlp atomically renames completed .part files.
            if size > MAX_BYTES:
                raise ValueError("La descarga excede 100 MB")
            await asyncio.sleep(.5)
    reader, watcher = asyncio.create_task(read()), asyncio.create_task(watch_size())
    try:
        done, _ = await asyncio.wait([reader, watcher], timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
        if not done:
            raise TimeoutError("Tiempo máximo de descarga/análisis agotado")
        for task in done:
            task.result()
        return reader.result()
    finally:
        for task in (reader, watcher):
            task.cancel()
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            await asyncio.wait_for(process.wait(), 2)
        except TimeoutError:
            os.killpg(process.pid, signal.SIGKILL)
            await process.wait()
        await asyncio.gather(reader, watcher, return_exceptions=True)


def window_positions(duration):
    if not 0 < duration <= MAX_DURATION:
        raise ValueError("Duración fuera de límite")
    starts = list(range(0, max(1, math.ceil(duration - FULL_WINDOW) + 1), FULL_HOP))
    last = max(0, duration - FULL_WINDOW)
    if last > starts[-1]:
        starts.append(last)
    return starts



def next_window(remaining, position):
    """Cover the audible moment first, then fill the rest of the exact recording."""
    covering = [start for start in remaining if start <= position < start + FULL_WINDOW]
    if covering:
        return max(covering)
    upcoming = [start for start in remaining if start > position]
    return min(upcoming) if upcoming else min(remaining)


async def current_playhead(track, fallback, duration):
    if not track.get('id'):
        return fallback
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=1)) as session:
            async with session.get('http://127.0.0.1:8975/status', allow_redirects=False) as response:
                response.raise_for_status()
                value = json.loads(await response.content.read(262144))
                current = value.get('track') or {}
                position = current.get('position')
                if (value.get('service') == 'singlayer' and current.get('id') == track['id']
                        and not current.get('stale') and isinstance(position, (int, float))
                        and math.isfinite(position)):
                    return min(duration, max(0, position)), bool(current.get("playing"))
    except (aiohttp.ClientError, TimeoutError, ValueError, TypeError):
        pass
    return fallback


def prepare_result(result, data):
    raw = result.get("raw_document", result.get("document"))
    return {**result, "document": compile_document(raw, data.get("catalog"), data.get("route")),
            "raw_document": compile_document(raw, route="transcript")}


def cached_result(directory, data):
    """An exact recording/model hit needs neither extraction nor source audio."""
    signature = data.get("engine_signature", "")
    for path in sorted(directory.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)[:16]:
        if path.stat().st_size > 4_000_000 or time.time() - path.stat().st_mtime > 86400:
            continue
        try:
            result = json.loads(path.read_text())
            if (result.get('url') != data['url'] or result.get('engine') != data['engine']
                    or result.get('engine_signature', '') != signature):
                continue
            recording_matches(result, data.get('track'))
            return prepare_result(result, data)
        except (ValueError, KeyError, TypeError, OSError):
            continue
    return None


def compile_document(raw, catalog=None, route="alignment", *, complete=True):
    if not raw:
        return None
    result = json.loads(json.dumps(raw))
    matched = 0
    for line in result["lines"]:
        match = unique_match(line["text"], catalog["lines"]) if catalog and route == "alignment" else None
        if match and match[1] == 1 and match[2] >= .85:
            text = catalog["lines"][match[0]]["text"]
            if text != line["text"]:
                line["words"] = []
            line["text"] = text
            matched += 1
    result.update(source="full-audio", sourceName=("Pista completa" if complete else "Análisis progresivo") + " · tiempos acústicos estimados",
                  timing="Word" if any(line.get("words") for line in result["lines"]) else "Line",
                  catalog_matches=matched)
    return result


async def analyze(data, emit):
    started = time.monotonic()
    url = valid_url(data["url"])
    cache_dir = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "singlayer/full-track"
    cache_dir.mkdir(parents=True, exist_ok=True)
    hit = cached_result(cache_dir, {**data, 'url': url})
    if hit is not None:
        emit({'full_result': hit, 'cached': True})
        return
    import sys

    local = Path(sys.executable).parent / "yt-dlp"
    executable = str(local) if local.is_file() else shutil.which("yt-dlp")
    if not executable or not shutil.which("ffmpeg"):
        raise RuntimeError("Faltan yt-dlp/ffmpeg para analizar la pista completa")
    base = [executable, "--ignore-config", "--no-playlist", "--no-warnings", "--socket-timeout", "15",
            "--retries", "2", "--no-progress"]
    if shutil.which("node"):
        base += ["--js-runtimes", "node"]
    emit({"full_progress": "Comprobando el enlace exacto", "percent": 0})
    info = json.loads(await run_command(base + ["--dump-single-json", "--skip-download", url], timeout=90))
    duration = recording_matches(info, data.get("track"))
    key = hashlib.sha256(json.dumps([url, info.get("id"), duration, data.get("engine"),
                                    data.get("engine_signature", ""), 2], sort_keys=True).encode()).hexdigest()
    cached = cache_dir / (key + '.json')
    with tempfile.TemporaryDirectory(prefix="audio-", dir=cache_dir) as directory:
        emit({"full_progress": "Descargando el audio completo", "percent": 2})
        metadata = Path(directory)/"source.json"
        metadata.write_text(json.dumps(info))
        await run_command(base + ["--load-info-json", str(metadata), "--max-filesize", str(MAX_BYTES), "-f", "bestaudio/best",
                                  "-o", str(Path(directory)/'track.%(ext)s')], timeout=300, directory=directory)
        files = [p for p in Path(directory).glob('track.*') if p.suffix not in ('.part', '.ytdl')]
        if len(files) != 1:
            raise ValueError("No se obtuvo una pista de audio individual completa")
        pcm = await run_command(['ffmpeg', '-v', 'error', '-i', str(files[0]), '-ar', '16000', '-ac', '1',
                                 '-f', 's16le', '-'], timeout=90, limit=MAX_DURATION*32000+32000)
        measured = len(pcm)/32000
        if abs(measured-duration) > max(2, duration*.02):
            raise ValueError("La descarga está incompleta o su duración no coincide")
        emit({'full_progress': 'Preparando el motor local', 'percent': 5})
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=2)) as session:
            for _ in range(240):
                try:
                    async with session.get('http://127.0.0.1:28748/health') as response:
                        health = await response.json()
                        if (response.status == 200 and health.get('service') == 'singlayer-transcription'
                                and health.get('ready') and not health.get('busy')):
                            if health.get('backend') != data['engine']:
                                raise ValueError("El motor activo no coincide con el solicitado")
                            break
                except (aiohttp.ClientError, TimeoutError):
                    pass
                await asyncio.sleep(.5)
            else:
                raise RuntimeError("El motor local no está listo")
        raw = None
        starts = window_positions(measured)
        remaining = starts.copy()
        clock_track = data.get('track') or {}
        position = max(0, clock_track.get('position', 0))
        playing = clock_track.get('playing', False)
        windows_done = 0
        recent_latency = 12
        while remaining:
            # Keep up with playback as extraction and inference consume wall time.
            playhead = min(measured, position + (time.monotonic()-started if playing else 0))
            playhead, currently_playing = await current_playhead(clock_track, (playhead, playing), measured)
            lead = min(12, recent_latency * .75) if currently_playing else 0
            start = next_window(remaining, min(measured, playhead + lead))
            remaining.remove(start)
            emit({"full_progress": f"Analizando audio · {windows_done+1}/{len(starts)} fragmentos", "percent": 5+int(90*windows_done/len(starts))})
            chunk = pcm[int(start*32000):int((start+FULL_WINDOW)*32000)]
            buf = io.BytesIO()
            with wave.open(buf,'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(chunk)
            inference_started = time.monotonic()
            doc = await transcribe_window(buf.getvalue(), start)
            recent_latency = time.monotonic() - inference_started
            raw = merge_transcript(raw, doc)
            windows_done += 1
            if doc:
                partial = {'document': compile_document(raw, data.get('catalog'), data.get('route'), complete=False),
                           'raw_document': compile_document(raw, route='transcript', complete=False), 'duration': measured}
                emit({'full_partial': partial, 'completed': windows_done, 'total': len(starts)})
        result = {'document': compile_document(raw, data.get('catalog'), data.get('route')),
                  'raw_document': compile_document(raw, route='transcript'),
                  'duration': measured, 'title': info.get('title'), 'url': url,
                  'engine': data['engine'], 'engine_signature': data.get('engine_signature', ''), 'windows': len(starts)}
        temporary = cached.with_suffix('.part')
        temporary.write_text(json.dumps(result, ensure_ascii=False))
        temporary.replace(cached)
        # Bound the persistent timing cache; temporary source audio is removed.
        entries = sorted(cache_dir.glob('*.json'), key=lambda p:p.stat().st_mtime)
        for old in entries[:-16]:
            old.unlink()
        emit({'full_result': result, 'cached': False})
