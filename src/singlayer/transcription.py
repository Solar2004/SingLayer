"""CrisperWhisper word timestamps anchored to the captured browser window."""

import io
import json
import math
import wave

import aiohttp

from .crisper_service import PORT, SERVICE


def transcript_document(payload, window_start, duration):
    if not all(math.isfinite(v) and v >= 0 for v in (window_start, duration)) or not 0 < duration <= 30:
        raise ValueError("Ventana temporal inválida")
    words = payload.get("words")
    if not isinstance(words, list) or len(words) > 1024:
        raise ValueError("CrisperWhisper no devolvió palabras válidas")
    groups, current = [], []
    previous_end = 0.0
    for word in words:
        start, end = float(word["start"]), float(word["end"])
        text = word["word"]
        if not isinstance(text, str) or len(text) > 2000 or any(ord(c) < 32 for c in text):
            raise ValueError("Texto de CrisperWhisper inválido")
        if not (math.isfinite(start) and math.isfinite(end) and 0 <= start <= end <= duration + 0.1):
            raise ValueError("CrisperWhisper devolvió tiempos fuera del fragmento")
        if start < previous_end:
            raise ValueError("Palabras de CrisperWhisper solapadas")
        previous_end = end
        if not text.strip() or end <= start:
            continue
        # Upstream strips spaces from word strings; restore display separators
        # by language without redistributing measured word spans.
        timed = {"start": window_start + start, "end": window_start + min(end, duration), "text": text}
        if current and (timed["start"] - current[-1]["end"] > .8 or len(current) >= 12):
            groups.append(current)
            current = []
        if (current and payload.get("language", "en") not in {"ja", "zh", "th", "lo", "my", "yue"}
                and not text.startswith(" ") and text[0] not in ".,!?;:"):
            timed["text"] = " " + text
        current.append(timed)
        if text.rstrip().endswith((".", "?", "!", "。", "？", "！")):
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    if not groups:
        return None
    lines = [{"index": i, "id": f"asr-{window_start:.3f}-{i}",
              "start": group[0]["start"], "end": group[-1]["end"],
              "text": "".join(w["text"] for w in group).strip(), "translation": "", "words": group}
             for i, group in enumerate(groups)]
    return {"source": "crisperwhisper-local", "sourceName": "Transcripción estimada · CrisperWhisper",
            "title": "", "artist": "", "timing": "Word", "lines": lines}


def whisper_document(payload, window_start, duration):
    """Keep measured segment bounds; BPE tokens are not separate spoken words."""
    if not all(math.isfinite(v) and v >= 0 for v in (window_start, duration)) or not 0 < duration <= 30:
        raise ValueError("Ventana temporal inválida")
    segments = payload.get("segments")
    if not isinstance(segments, list) or len(segments) > 1024:
        raise ValueError("Whisper.cpp devolvió segmentos inválidos")
    lines = []
    previous = 0.0
    for segment in segments:
        if float(segment.get("no_speech_prob", 0)) > .6:
            continue
        start, end = float(segment["start"]), float(segment["end"])
        tokens = segment.get("words", [])
        centers = [token.get("t_dtw", -1) for token in tokens]
        dtw = bool(centers and all(type(value) is int and 0 <= value <= duration * 100 + 10
                                  for value in centers)
                   and centers == sorted(centers) and centers[-1] > centers[0])
        if dtw:
            # DTW supplies acoustic token centers, not exact word boundaries.
            # Use their observed envelope as explicitly estimated line timing;
            # never spread the leading instrumental silence over lyric tokens.
            start, end = centers[0] / 100, centers[-1] / 100
        text = segment["text"].strip()
        if not text:
            continue
        if (not all(math.isfinite(v) for v in (start, end))
                or not previous <= start < end <= duration + .1
                or len(text) > 2000 or any(ord(c) < 32 for c in text)):
            raise ValueError("Whisper.cpp devolvió tiempos o texto inválidos")
        previous = end
        words = []
        token_end = start
        valid_tokens = True
        for token in tokens:
            t0, t1 = float(token.get("start", -1)), float(token.get("end", -1))
            value = token.get("word", "")
            if (not isinstance(value, str) or not all(math.isfinite(v) for v in (t0, t1))
                    or not token_end <= t0 <= t1 <= end + .1):
                valid_tokens = False
                break
            token_end = t1
            if t1 <= t0 or not value:
                continue
            if words and not value.startswith(" "):
                words[-1]["text"] += value
                words[-1]["end"] = window_start + min(t1, duration)
            else:
                words.append({"text": value, "start": window_start + t0,
                              "end": window_start + min(t1, duration)})
        if dtw or not valid_tokens or "".join(w["text"] for w in words).strip() != text:
            words = []
        lines.append({"index": len(lines), "id": f"whisper-{window_start:.3f}-{len(lines)}",
                      "start": window_start + start, "end": window_start + min(end, duration),
                      "text": text, "translation": "", "words": words})
    if not lines:
        return None
    return {"source": "whisper-vulkan", "sourceName": "Transcripción estimada · Whisper.cpp Vulkan",
            "title": "", "artist": "", "timing": "Word" if any(line["words"] for line in lines) else "Line",
            "lines": lines}


def wav_duration(wav_bytes):
    if len(wav_bytes) > 1_000_000:
        raise ValueError("Fragmento demasiado grande")
    with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
        if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) != (1, 2, 16000):
            raise ValueError("Se requiere PCM mono de 16 kHz y 16 bits")
        duration = wav.getnframes() / 16000
    if not 0 < duration <= 30:
        raise ValueError("Fragmento fuera del límite de 30 segundos")
    return duration


async def transcribe_window(wav_bytes, window_start):
    """Only the dedicated local service, bounded request/response, no redirects."""
    duration = wav_duration(wav_bytes)
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=90)) as session:
        async with session.post(
            f"http://127.0.0.1:{PORT}/inference", data=wav_bytes,
            headers={"Content-Type": "audio/wav"}, allow_redirects=False
        ) as response:
            if response.status != 200:
                raise RuntimeError(f"El motor local respondió HTTP {response.status}")
            output = bytearray()
            async for chunk in response.content.iter_chunked(8192):
                output.extend(chunk)
                if len(output) > 1_000_000:
                    raise ValueError("Respuesta de CrisperWhisper demasiado grande")
    payload = json.loads(output)
    if payload.get("service") != SERVICE:
        raise ValueError("Servicio de transcripción inesperado")
    if payload.get("backend") == "whisper.cpp":
        return whisper_document(payload, window_start, duration)
    return transcript_document(payload, window_start, duration)
