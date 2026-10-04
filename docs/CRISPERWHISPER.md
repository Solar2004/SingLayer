# CrisperWhisper 2.0 — alternativa CPU

Estado actual: el usuario autorizó Whisper.cpp Vulkan para canciones; es el motor
seleccionado cuando está instalado. Crisper small CPU sigue disponible con
`SINGLAYER_ENGINE=crisper`. Ambos comparten `singlayer-transcription` en28748.
Véase [AUTOMATIC_TIMING.md](AUTOMATIC_TIMING.md). El runtime Crisper small está
instalado y probado; las restricciones DNS inferiores son historia.

## Implementación e instalación histórica

Sustituye a whisper.cpp en el panel y en el transporte. No se mantiene un fallback
silencioso al motor anterior. Los archivos de compilación y modelos anteriores
permanecen en `.build/` como evidencia histórica; ya no se invocan.

```sh
bash scripts/setup-crisper.sh
bash scripts/run-crisper.sh
```

El instalador crea Python3.12 aislado, instala CrisperWhisper2.0.3 y el fork
ctranslate2-crisperwhisper4.7.1.post3, descarga el modelo oficial multilingüe
`nyralabs/CrisperWhisper2.0_small` y convierte a CPU int8. PyTorch CPU se usa para
la conversión. La revisión Hugging Face queda fijada en model-lock.json al primer
setup; ready.json solo se publica tras conversión y carga correctas. El servicio
carga exclusivamente archivos locales, no descarga durante reproducción.

Servidor persistente en127.0.0.1:28748, health con identidad propia, una inferencia
a la vez, solicitudes WAV<=1MB/30s. Entrada mono16kHz PCM16. Audio transitorio en
memoria; sin micrófono, archivos de música ni subida a nube. Detección de idioma
mediante CT2 antes de transcribir, modo verbatim y word_timestamps=True. Esta
integración usa la interfaz interna `_engine` de la versión fijada para detección;
verificar de nuevo antes de actualizar CrisperWhisper.

El adaptador conserva tiempos reales por palabra anclados al reloj del navegador,
agrupa palabras para visualización y rechaza tiempos fuera de la ventana. Los
cambios de pista/pausa/seek invalidan resultados. Las coincidencias exactas de una
línea del catálogo conservan tiempos por palabra; coincidencias aproximadas usan
solo tiempos por línea. No se inventan tiempos de palabras distintas.

## Hardware y precisión

El runtime rápido oficial usa CPU/CUDA, sin backend Vulkan para la RX590. CPU
int8 se muestra explícitamente en el panel. No se afirma aceleración AMD ni mayor
velocidad frente al antiguo whisper.cpp Vulkan. Modelo small elegido para acotar
coste de CPU; no hay benchmark de canto propio todavía.

Tiempos por palabra no eliminan el retraso de captura (ventanas12s cada8s) ni
garantizan la precisión con voces alteradas, música fuerte o remixes. Los resultados
son estimados. Las mediciones oficiales de precisión se refieren a habla.

## Estado de instalación, 2026-10-04

Código y pruebas de contrato implementados. Instalación real bloqueada por DNS
al obtener PyTorch; solicitud de red no concedida. Entorno creado, dependencias
/modelo aún NO instalados; no existe ready.json. El panel informa que falta el
motor. Falta ejecutar setup y probar inferencia real y latencia de canto.

Fuentes primarias:
- https://github.com/nyrahealth/CrisperWhisper
- https://github.com/nyrahealth/CrisperWhisper/blob/main/crisperwhisper/model.py
- https://github.com/nyrahealth/CrisperWhisper/blob/main/crisperwhisper/engine.py
- https://opennmt.net/CTranslate2/python/ctranslate2.models.Whisper.html

Código upstream MIT. Pesos2.0 bajo Nyra Health Non-Commercial Research License;
no distribuirlos como MIT ni utilizarlos comercialmente sin licencia apropiada.

## Ruta GPU comunitaria investigada

Ver [GPU.md](GPU.md). Hay una receta C++ Vulkan experimental; no está compilada
ni validada. El backend del panel sigue CPU hasta comprobar inferencia real.
