# SingLayer readiness — 2026-10-04

Estado actual: [sincronización automática](AUTOMATIC_TIMING.md).

- 202 pruebas completas pasan, sin exclusiones; Ruff, shell y diff check aprobados.
- Whisper.cpp large-v3-turbo Q5_0 instalado y probado con RX590 Vulkan y DTW.
- Vista de frases con inicio/final, duración real y reloj automático estimado.
- Night Changes sped up: cinco referencias, velocidad1.233×, desfase2.842s;
  referencia independiente a0.219s del tiempo acústico observado.
- Night Dancer sped up: japonés detectado y tres líneas del catálogo alineadas.
- Pronunciación local funciona también con letras transcritas y reloj automático.
- Shazam identificó10/10 muestras de la matriz anterior; captura PipeWire nativa,
  selector de navegador y normalización de variantes comprobados.
- Renderer X11 revisado; compositor KWin Wayland de prueba confirmó layer shell
  y prueba de ciclos de blur. Panel reiniciado con motor instalado.
- Crisper small CPU conservado como selección explícita; Crisper Vulkan sigue
  sin una fuente original descargable. No se presenta Crisper CPU como GPU.

La precisión universal no está demostrada. Honeypie slowed/reverb y After Dark
muy muffled dieron transcripciones incompletas. El reloj supone velocidad
constante y no puede anticipar cortes futuros desconocidos. Se conserva ajuste
manual; los resultados automáticos se presentan como estimados.

No se comprometen audio, letras completas ni pesos. Detalles y pins en el enlace.
