"""Owned persistent Vulkan whisper.cpp process behind the bounded local API."""
import asyncio
import ctypes
import json
import os
import signal
import socket
import wave

import aiohttp
from aiohttp import web

from .crisper_service import PORT, SERVICE
from .transcriber_runtime import selected_engine
from .transcription import wav_duration


def parent_death_signal():
    # Linux: forced panel/service shutdown must not orphan a loaded GPU worker.
    parent = os.getppid()
    libc = ctypes.CDLL(None)
    if libc.prctl(1, signal.SIGTERM, 0, 0, 0) != 0:
        raise OSError("No se pudo asociar la vida del motor a su servicio")
    if os.getppid() != parent or parent == 1:
        os.kill(os.getpid(), signal.SIGTERM)


def create_app(config):
    app = web.Application(client_max_size=1_000_000)
    busy = False
    native = None
    used_gpu = False
    drain = None
    # An ephemeral loopback port avoids interfering with existing native servers.
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        native_port = probe.getsockname()[1]
    url = f"http://127.0.0.1:{native_port}"

    async def logs():
        nonlocal used_gpu
        while line := await native.stderr.readline():
            if b"using Vulkan" in line and b"backend" in line:
                used_gpu = True
            # Never retain native logs, which may include recognized lyrics.

    async def stop(_):
        if native and native.returncode is None:
            native.terminate()
            try:
                await asyncio.wait_for(native.wait(), 5)
            except TimeoutError:
                native.kill()
                await native.wait()
        if drain:
            drain.cancel()
            await asyncio.gather(drain, return_exceptions=True)

    async def start(_):
        nonlocal native, drain
        native = await asyncio.create_subprocess_exec(
            config["binary"], "-m", config["model_path"], "--host", "127.0.0.1",
            "--port", str(native_port), "--language", "auto", "--no-flash-attn",
            "--dtw", "large.v3.turbo", "-t", "4",
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
            preexec_fn=parent_death_signal,
        )
        drain = asyncio.create_task(logs())
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=2)) as session:
                for _ in range(240):
                    if native.returncode is not None:
                        raise RuntimeError("Whisper.cpp terminó al cargar el modelo")
                    try:
                        async with session.get(url + "/health") as response:
                            if response.status == 200:
                                if not used_gpu:
                                    raise RuntimeError("Whisper.cpp no confirmó ejecución Vulkan")
                                return
                    except aiohttp.ClientError:
                        pass
                    await asyncio.sleep(.5)
            raise TimeoutError("Whisper.cpp no inició a tiempo")
        except BaseException:
            await stop(app)
            raise

    async def health(request):
        if not native or native.returncode is not None or not used_gpu:
            raise web.HTTPServiceUnavailable()
        return web.json_response({"service": SERVICE, "backend": "whisper.cpp", "device": "vulkan",
                                  "model": config["model"], "ready": True, "busy": busy,
                                  "inference_profile": config.get("inference_profile", "baseline")})

    async def inference(request):
        nonlocal busy
        if request.headers.get("Origin"):
            raise web.HTTPForbidden()
        if busy or not native or native.returncode is not None:
            raise web.HTTPServiceUnavailable()
        if request.content_type != "audio/wav":
            raise web.HTTPUnsupportedMediaType()
        busy = True
        try:
            audio = await request.read()
            try:
                wav_duration(audio)
            except (ValueError, EOFError, wave.Error):
                raise web.HTTPBadRequest() from None
            form = aiohttp.FormData()
            form.add_field("file", audio, filename="window.wav", content_type="audio/wav")
            for key, value in {"response_format": "verbose_json", "language": "auto",
                               "token_timestamps": "true", "suppress_nst": "true"}.items():
                form.add_field(key, value)
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=85)) as session:
                async with session.post(url + "/inference", data=form, allow_redirects=False) as response:
                    response.raise_for_status()
                    raw = bytearray()
                    async for chunk in response.content.iter_chunked(8192):
                        raw.extend(chunk)
                        if len(raw) > 1_000_000:
                            raise web.HTTPBadGateway()
                    result = json.loads(raw)
            return web.json_response({**result, "service": SERVICE, "backend": "whisper.cpp"})
        except (aiohttp.ClientError, TimeoutError, ValueError):
            raise web.HTTPBadGateway(text="El motor de audio no respondió correctamente") from None
        finally:
            busy = False

    app.on_startup.append(start)
    app.on_cleanup.append(stop)
    app.router.add_get("/health", health)
    app.router.add_post("/inference", inference)
    return app


def main():
    web.run_app(create_app(selected_engine()), host="127.0.0.1", port=PORT, handler_cancellation=False, shutdown_timeout=1)


if __name__ == "__main__":
    main()
