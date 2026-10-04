"""Local dictionary phonemes; Spanish-readable approximation, never translation."""

import ctypes
import re
from pathlib import Path


def spanish_reading(ipa):
    replacements = {
        "tʃ": "ch", "dʒ": "y", "aɪ": "ai", "eɪ": "ei", "ɔɪ": "oi", "aʊ": "au", "oʊ": "ou",
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


def local_guide(texts):
    import espeakng_loader
    from langid.langid import LanguageIdentifier, model

    detector = LanguageIdentifier.from_modelstring(model, norm_probs=True)
    overall = detector.classify(" ".join(texts))[0]
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
            if confidence < .85 and len(text.split()) < 5:
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
                        "tip": f"Idioma {language} · guía aproximada. h aspirada; sh/ch distintos; th/dh ingleses; ~ nasal; ü redondeada."}
            cache[text] = item
            guide.append(item)
    finally:
        lib.espeak_Terminate()
    return guide
