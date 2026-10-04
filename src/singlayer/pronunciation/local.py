"""Local dictionary phonemes; Spanish-readable approximation, never translation."""

import ctypes
import re
from pathlib import Path


def spanish_reading(ipa):
    replacements = {
        "tʃ": "ch", "tɕ": "ch", "ʈʂ": "ch", "dʒ": "y", "ɕ": "sh", "ʂ": "sh", "ʐ": "zh", "ʲ": "y", "ɨ": "i", "ʏ": "ü", "aɪ": "ai", "eɪ": "ei", "ɔɪ": "oi", "aʊ": "au", "oʊ": "ou",
        "əʊ": "ou", "ʃ": "sh", "ʒ": "zh", "θ": "th", "ð": "dh", "ŋ": "ng", "ɲ": "ñ",
        "ɹ": "r", "ɾ": "r", "ʁ": "r", "ɣ": "g", "ɡ": "g", "ɪ": "i", "ʊ": "u", "ɛ": "e",
        "æ": "a", "ɑ": "a", "ɒ": "o", "ɔ": "o", "ʌ": "a", "ə": "a", "ɜ": "e", "ɐ": "a",
        "ø": "eu", "œ": "eu", "ɥ": "ü", "y": "ü", "ɯ": "u", "β": "b", "ç": "hy", "x": "j",
        "j": "y", "w": "u", "ɫ": "l", "ʔ": "", "ː": "", "ˑ": "", "ˌ": "", "̃": "~",
    }
    pattern = "|".join(re.escape(key) for key in sorted(replacements, key=len, reverse=True))
    result = re.sub(pattern, lambda m: replacements[m.group()], ipa)
    accents = dict(zip("aeiou", "áéíóú"))
    result = re.sub(r"ˈ([^aeiou\s]*)([aeiou])", lambda m: m[1] + accents[m[2]], result)
    return result.replace("ˈ", "").strip()


LANGUAGE_TIPS = {
    "en": "h aspirada; sh/ch distintos; th/dh dentales; r sin vibración española.",
    "fr": "~ indica nasalización; ü: labios como u y lengua como i; r francesa. Los finales mudos se omiten.",
    "ru": "y tras consonante indica suavización, no otra sílaba; ы se aproxima con i, pero no es la i española.",
    "de": "ü/eu: vocales redondeadas; j aproxima ch fuerte; hy indica ch suave.",
    "it": "Mantén consonantes dobles y vocales claras; el acento escrito orienta la lectura.",
    "pt": "~ indica nasalización; sh/zh representan sonidos distintos de s; vocales reducidas aproximadas.",
}


def local_guide(texts):
    import espeakng_loader
    from langid.langid import LanguageIdentifier, model

    detector = LanguageIdentifier.from_modelstring(model, norm_probs=True)
    overall, overall_confidence = detector.classify(" ".join(texts))
    lib = espeakng_loader.load_library()
    if lib is None:
        raise RuntimeError("Motor fonético local no disponible")
    lib.espeak_Initialize.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
    lib.espeak_Initialize.restype = ctypes.c_int
    lib.espeak_SetVoiceByName.argtypes = [ctypes.c_char_p]
    lib.espeak_SetVoiceByName.restype = ctypes.c_int
    lib.espeak_TextToPhonemes.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.c_int, ctypes.c_int]
    lib.espeak_TextToPhonemes.restype = ctypes.c_char_p
    lib.espeak_Terminate.argtypes = []
    if lib.espeak_Initialize(2, 0, str(Path(espeakng_loader.get_data_path()).parent).encode(), 0x8000) < 0:
        raise RuntimeError("No se pudo cargar el diccionario fonético")
    guide = []
    cache = {}
    try:
        for text in texts:
            if not text.strip():
                guide.append({"phonetic": "", "tip": ""})
                continue
            if text in cache:
                guide.append(cache[text])
                continue
            language, confidence = detector.classify(text)
            words = re.findall(r"[^\W\d_]+", text.casefold())
            repetitive_latin = text.isascii() and len(set(words)) <= 3
            # Language scores for short refrains can be confidently wrong.
            # Prefer a confident song context for repetitive Latin phrases;
            # keep informative foreign lines and other scripts independent.
            if (confidence < .85 and len(text.split()) <= 5
                    or repetitive_latin and overall_confidence >= .85):
                language = overall
            if language == "ja":
                from pykakasi import kakasi

                converted = kakasi().convert(text)
                reading = " ".join(part["hepburn"] for part in converted)
                item = {"phonetic": reading, "tip": "Japonés romanizado: j suena como y; h aspirada; vocales largas se mantienen. Lectura de kanji aproximada."}
            elif language == "es":
                item = {"phonetic": text, "tip": "Texto español conservado."}
            elif language not in {"en", "fr", "de", "it", "pt", "ru"} or lib.espeak_SetVoiceByName(language.encode()) != 0:
                item = {"phonetic": text, "tip": f"Idioma {language}: sin diccionario disponible; original conservado."}
            else:
                buffer = ctypes.create_string_buffer(text.encode())
                pointer = ctypes.cast(buffer, ctypes.c_void_p)
                chunks = []
                for _ in range(100):
                    if not pointer.value:
                        break
                    raw = lib.espeak_TextToPhonemes(ctypes.byref(pointer), 1, 2)
                    if raw:
                        chunks.append(raw.decode())
                else:
                    raise ValueError("Texto fonético fuera de límite")
                phonemes = " ".join(chunks)
                item = {"phonetic": spanish_reading(phonemes) or text,
                        "tip": f"Idioma {language} · guía aproximada. {LANGUAGE_TIPS[language]}"}
            cache[text] = item
            guide.append(item)
    finally:
        lib.espeak_Terminate()
    return guide
