"""Opt-in local phonetic guide; original lyrics and timestamps remain authoritative."""

import asyncio
import copy
import json
import re
import time
from importlib.resources import files

import aiohttp

from ..diagnostics import record


def parse_guide(raw, texts):
    raw = re.sub(r"<\|stats\|>.*?(?:<\|/stats\|>|$)", "", raw, flags=re.S).strip()
    if raw.startswith("```") and raw.endswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I)[:-3].strip()
    parsed = json.loads(raw)
    lines = parsed.get("lines") if isinstance(parsed, dict) else None
    if not isinstance(lines, list) or len(lines) != len(texts):
        raise ValueError("La IA cambió el número de líneas")
    for index, item in enumerate(lines):
        if not isinstance(item, dict) or type(item.get("id")) is not int or item["id"] != index:
            raise ValueError("La IA cambió el orden de las líneas")
        phonetic, tip = item.get("phonetic"), item.get("tip", "")
        if not isinstance(phonetic, str) or not phonetic.strip() or len(phonetic) > 1000:
            raise ValueError("Guía fonética no válida")
        if not isinstance(tip, str) or len(tip) > 300:
            raise ValueError("Consejo no válido")
        if any(ord(c) < 32 for c in phonetic + tip):
            raise ValueError("La guía contiene caracteres de control")
    return [{"phonetic": item["phonetic"], "tip": item.get("tip", "")} for item in lines]


async def request_guide(session, texts):
    rules = files(__package__).joinpath("SKILL.md").read_text(encoding="utf-8")
    body = {
        "messages": [
            {
                "role": "user",
                "content": json.dumps(
                    {"lines": [{"id": index, "text": text} for index, text in enumerate(texts)]},
                    ensure_ascii=False,
                ),
            }
        ],
        "chatOptions": {"selectedModel": "llama3.1-8B", "systemPrompt": rules, "topK": 8},
        "attachment": None,
    }
    async with session.post(
        "https://chatjimmy.ai/api/chat",
        json=body,
        allow_redirects=False,
        headers={"Origin": "https://chatjimmy.ai", "Referer": "https://chatjimmy.ai/"},
    ) as response:
        record("pronunciation_http", "response", status=response.status)
        if response.status == 429:
            raise RuntimeError("ChatJimmy está limitando solicitudes; reintenta más tarde")
        if response.status in (401, 403):
            raise RuntimeError("ChatJimmy rechazó el acceso; no es un fallo de la letra")
        if 300 <= response.status < 400:
            raise RuntimeError("ChatJimmy redirigió la petición; revisa la disponibilidad del servicio")
        response.raise_for_status()
        output = bytearray()
        async for chunk in response.content.iter_chunked(8192):
            output.extend(chunk)
            if len(output) > 100_000:
                raise ValueError("Respuesta de IA demasiado grande")
    return parse_guide(output.decode("utf-8"), texts)


async def generate(document):
    from .local import local_guide

    texts = [line["text"] for line in document["lines"]]
    if not texts or len(texts) > 1000 or sum(map(len, texts)) > 30_000:
        raise ValueError("Letra demasiado larga para esta guía")
    started = time.monotonic()
    return {"guide": local_guide(texts), "elapsed": round(time.monotonic() - started, 3), "engine": "espeak-ng"}


async def generate_remote(document):
    texts = [line["text"] for line in document["lines"]]
    if not texts or len(texts) > 1000 or sum(map(len, texts)) > 30_000:
        raise ValueError("Letra demasiado larga para esta guía")
    unique = list(dict.fromkeys(text for text in texts if text.strip()))
    record("pronunciation", "started")
    started = time.monotonic()
    slots = asyncio.Semaphore(2)
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=35)) as session:

        async def batch(chunk):
            async with slots:
                try:
                    return await request_guide(session, chunk)
                except (ValueError, UnicodeError):
                    record("pronunciation", "invalid_response_retry_split")
                    # A malformed large answer gets one bounded smaller retry.
                    # Do not retry access errors or turn rate limits into a flood.
                    if len(chunk) < 2:
                        raise
                    middle = len(chunk) // 2
                    return await request_guide(session, chunk[:middle]) + await request_guide(
                        session, chunk[middle:]
                    )

        tasks = [asyncio.create_task(batch(unique[i : i + 12])) for i in range(0, len(unique), 12)]
        try:
            results = await asyncio.wait_for(asyncio.gather(*tasks), 90)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
    lookup = dict(zip(unique, [item for result in results for item in result]))
    record("pronunciation", "completed")
    return {
        "guide": [lookup[text] if text.strip() else {"phonetic": "", "tip": ""} for text in texts],
        "elapsed": round(time.monotonic() - started, 3),
    }


def apply_guide(document, guide, bilingual=False):
    if not document or not guide or len(guide) != len(document["lines"]):
        return document
    result = copy.deepcopy(document)
    result["timing"] = "Line"
    for line, item in zip(result["lines"], guide):
        original = line["text"]
        line["text"] = original if bilingual else item["phonetic"]
        line["translation"] = item["phonetic"] if bilingual else ""
        # The model has no authority to generate word timings.
        line["words"] = []
    return result
