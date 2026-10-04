# Solicitudes y estado

Últimas decisiones del usuario: permitir otro motor probado para canciones y
mostrar qué frase corresponde a cada segundo, con duración y sincronización
automática. Esta decisión reemplaza la restricción anterior de usar solo Crisper.

Implementado: Whisper.cpp large-v3-turbo Q5_0 Vulkan/DTW, reloj estimado desde
referencias acústicas únicas, vista de inicio/final, recorte por duración,
calibración manual persistida, caché de tramos y pronunciación local.

Estado y evidencia: [AUTOMATIC_TIMING.md](AUTOMATIC_TIMING.md).
Handoff canónico: [HANDOFF.md](../HANDOFF.md). 209 pruebas completas pasan.

Las muestras muy distorsionadas aún pueden necesitar ajuste manual. No se afirma
precisión perfecta para todas las variantes ni tiempos exactos por palabra DTW.
