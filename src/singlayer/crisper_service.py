"""Persistent, loopback-only CrisperWhisper 2.0 service; one loaded model."""

import asyncio
import io
import json
import wave
from pathlib import Path

from aiohttp import web

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / ".build/crisperwhisper/ready.json"
SERVICE = "singlayer-transcription"
PORT = 28748


def load_model():
    from crisperwhisper import CrisperWhisperModel

    config = json.loads(CONFIG.read_text())
    # AMD Vulkan is not a CTranslate2 backend. Never label CPU as GPU.
    if config["device"] != "cpu" or not Path(config["model_path"]).is_dir():
        raise ValueError("Configuración CrisperWhisper inválida")
    return CrisperWhisperModel(config["model_path"], backend="ct2", device="cpu", compute_type="int8")


def infer(model, audio):
    import numpy as np

    with wave.open(io.BytesIO(audio), "rb") as wav:
        if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) != (1, 2, 16000):
            raise ValueError("Se requiere WAV mono PCM16 de 16 kHz")
        frames = wav.getnframes()
        if not 0 < frames <= 30 * 16000:
            raise ValueError("Ventana fuera de límites")
        pcm = wav.readframes(frames)
    if len(pcm) != frames * 2:
        raise ValueError("Audio incompleto")
    samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768
    # The public transcribe API defaults to English; use CT2's acoustic
    # language detector instead of accidentally forcing every song to English.
    engine = model._engine  # Pinned CrisperWhisper 2.0.3 CT2 seam.
    probabilities = engine.model.detect_language(engine.extract_features(samples))[0]
    if not probabilities:
        raise ValueError("Idioma no detectado")
    language = probabilities[0][0].removeprefix("<|").removesuffix("|>")
    result = model.transcribe(samples, sr=16000, language=language,
                              word_timestamps=True, mode="verbatim")
    return {"service": SERVICE, "language": result.language,
            "words": [{"word": w.word, "start": w.start, "end": w.end} for w in result.words or []]}


def create_app(model):
    app = web.Application(client_max_size=1_000_000)
    busy = False

    async def health(request):
        return web.json_response({"service": SERVICE, "device": "cpu", "backend": "crisperwhisper", "ready": True, "busy": busy})

    async def inference(request):
        nonlocal busy
        if request.headers.get("Origin"):
            raise web.HTTPForbidden()
        if busy:
            raise web.HTTPServiceUnavailable(text="CrisperWhisper ocupado")
        busy = True
        try:
            if request.content_type != "audio/wav":
                raise web.HTTPUnsupportedMediaType()
            audio = await request.read()
            try:
                output = await asyncio.to_thread(infer, model, audio)
            except (ValueError, wave.Error, EOFError):
                raise web.HTTPBadRequest(text="Audio inválido") from None
            return web.json_response(output)
        finally:
            busy = False

    app.router.add_get("/health", health)
    app.router.add_post("/inference", inference)
    return app


def main():
    # Model load before readiness: no downloads in the playback path.
    import os

    os.environ["HF_HUB_OFFLINE"] = "1"
    model = load_model()
    web.run_app(create_app(model), host="127.0.0.1", port=PORT, handler_cancellation=False)


if __name__ == "__main__":
    main()
