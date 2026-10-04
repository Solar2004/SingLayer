# Solicitudes y estado

Última instrucción: sustituir Whisper por CrisperWhisper. Código migrado a2.0,
tiempos por palabra, CPU int8 explícito. Runtime/modelo aún no instalado por DNS;
98 tests disponibles pasan. Ver docs/CRISPERWHISPER.md. Las referencias posteriores
a Whisper/Vulkan describen el trabajo anterior, ya reemplazado.

Estado actual y próximos pasos: [HANDOFF.md](../HANDOFF.md).

Implementados: panel automático, catálogos, variantes SoundCloud, reconocimiento
compatible Python3.12, Whisper persistente Vulkan/CPU, fallback continuo acotado,
invalidación por playback, alineación conservadora por tramos, calibración manual,
pronunciación local y vista dual.

Pruebas reales: GPU frente CPU, búsqueda de cinco variantes SoundCloud, captura
live de una variante sped-up, reconocimiento y muestras fonéticas. La recuperación
ante tiempos ASR inválidos está probada con regresión; falta repetir el caso real
slowed que descubrió el fallo. Precisión general musical, validación compositor y
referencia de audio original siguen pendientes. No afirmar compatibilidad perfecta.
