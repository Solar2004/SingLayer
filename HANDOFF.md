# SingLayer — handoff completo

Actualizado: 2026-10-04 (validación completa y runtime instalado). Este archivo es el punto de entrada canónico y debe leerse
antes de docs/REQUESTS.md o documentación histórica. No se necesita la conversación.

## Última prueba musical — 2026-10-04

Siete ventanas reales, cuatro canciones: Shazam6/6; alineación parcial inglesa y
japonesa, cero coincidencias fiables en After Dark/Honeypie alteradas. Recortes
y reconstrucción de reloj probados al rebasing de ASR musical real. Contexto de
estribillos sin caso positivo en esta tanda. Ver docs/MUSIC_VALIDATION_CURRENT.md.

## Estado actual — sincronización automática 2026-10-04

Esta sección reemplaza las restricciones y decisiones históricas inferiores.
El usuario autorizó un motor alternativo probado para canciones y pidió una línea
de tiempo automática por segundos/duración.

- **141 pruebas completas pasan**, Ruff, shell y diff check OK.
- **Whisper.cpp large-v3-turbo Q5_0 instalado y seleccionado en RX590 Vulkan**.
  API real/DTW validado, SHA256 y revisiones fijadas. Crisper small CPU conservado;
  `SINGLAYER_ENGINE=crisper` lo selecciona. GPU de Crisper sigue sin fuente original
  descargable; ya no bloquea la ruta GPU elegida por el usuario.
- API común `singlayer-transcription`,28748. Wrapper persistente y proceso nativo
  propio en puerto efímero. No fallback silencioso de Vulkan a CPU. Audio <=30s,
  una petición a la vez, cola acotada, cleanup y señal de muerte del padre.
- Ventanas Whisper24s/avance16s. DTW excluye silencio inicial y produce tiempos
  estimados por línea. No confundir centros DTW con límites exactos por palabra.
- Reloj completo automático con >=3 referencias únicas coherentes, separación15s,
  residual<=750ms. Repeticiones solas no califican; contradicciones invalidan reloj;
  títulos remix/mashup/loop/cut/snippet usan solo tramos. Futuro constante estimado,
  nunca garantía de ausencia de cortes no etiquetados.
- Night Changes real:5 referencias, velocidad1.23305588585, desfase2.84205707491s.
  Referencia reservada fuera del fit: diferencia0.219s frente al DTW observado.
- Japonés real: Night Dancer,2 líneas ASR y3 del catálogo alineadas, guía local2;
  inglés6 líneas/guías por ventana. No hay WER contra anotación humana.
- Vista ≡ muestra inicio/final, recorta a duración real, conserva tramos observados
  al hacer seek (RAM16 grabaciones/512líneas). Ajustes manuales persistidos para32
  identidades exactas de grabación/catálogo, sin guardar audio ni letras allí.
- Guía local también en live/automático; protección contra guía de texto anterior.
- PipeWire nativo y selector de browser funcionan. Shazam matriz anterior10/10.
- Renderer X11 revisado; KWin Wayland de prueba layer shell y ciclos blur aprobados.
- Panel reiniciado. Solo se detuvieron procesos propios, no otros navegadores/apps.

Estado operativo y límites: docs/AUTOMATIC_TIMING.md. El canto extremadamente
alterado continúa siendo difícil; HoneyPie/After Dark adicionales dieron texto
incompleto. Nunca prometer todas las canciones perfectas. El ajuste manual sigue
siendo la recuperación disponible. Archivos inferiores son historia, no el estado
actual de red, GPU, modelo o instrucciones del usuario.

## 1. Objetivo y decisiones del usuario

App karaoke Linux/KDE (Wayland y X11) mientras escucha SoundCloud en Brave;
también busca Spotify/YouTube. Panel automático mínimo monocromático, portada y
espectro reales, overlay, multilinea y ajustes en ⋯. Reutilizar motores existentes.

Quiere letras correctas pese a uploads mal nombrados, versiones sped-up/slowed,
pitch/reverb/muffled, remixes con cortes/estribillos reordenados. Reconocimiento
identifica canciones; los catálogos dan letras; ASR local ayuda como último recurso
y para medir tiempos. No prometer precisión universal ni palabras futuras en vivo.

Pronunciación: aproximación legible por hispanohablantes, conservando idioma
original; original, guía o ambos, sin traducción ni solapamiento visual.

**Últimas instrucciones:** sustituir Whisper por CrisperWhisper, buscar una vía GPU
para RX590 incluso C++, preparar handoff completo y hacer push. Push y commit están
autorizados. No volver silenciosamente al modelo Whisper base ni presentar CPU como
GPU. No cambiar drivers ni borrar cambios del usuario para alcanzar ese objetivo.

## 2. Repositorio y publicación

Remoto público: https://github.com/Solar2004/SingLayer.git, rama main.
En esta máquina: outputs/SingLayer dentro de la tarea original de2026-10-03.
Git conserva el trabajo acumulado de varias continuaciones. Antes del commit final
local, HEAD era30609a6, seguido de30565e3; origin/main local seguía en4711b6a.
El estado remoto real no puede verificarse por DNS. El commit preparado incluye el
handoff y la integración/pruebas/documentación acumuladas. Consultar `git log -3`
para su hash; no poner el hash del propio documento dentro del mismo commit.

**Publicación bloqueada:** git ls-remote falló con “Could not resolve host:
github.com”. La solicitud de acceso de red/dispositivo no fue concedida. Se intenta
push normal a origin/main, sin force; si falla por el mismo motivo el commit queda
local. Nunca anunciar publicación remota sin éxito confirmado. Al recuperar red:

```sh
git fetch origin
git log --oneline --left-right main...origin/main
git push origin main
```

Si main remoto diverge, revisar y conservar los cambios de ambas ramas antes de
publicar. No hacer force-push. `.build`, `.venv`, modelos, audio, cachés, credenciales
y lanzador generado están ignorados y no se publican.

## 3. Estado verificable

| Parte | Estado actual | Evidencia/límite |
|---|---|---|
| Panel/bridge/portada | Implementado | Protocolos y pruebas; portada fue confirmada en sesión anterior |
| FFT navegador | Implementado | Selección de flujo real y pruebas de señal; no animación ficticia |
| Catálogos y búsqueda | Implementado | LRCLIB/NetEase/KuGou/syncedlyrics; cinco variantes SoundCloud reales consultadas |
| Shazam | Implementado | Hasta3 muestras12s; consenso recording ID, candidato ≠ confirmado |
| Runtime reconocimiento | Instalado localmente antes | Python3.12 aislado; Python3.14 tuvo segfault nativo; un reconocimiento real respondió |
| Calibración manual | Implementado | Dos referencias>=15s, velocidad.5–2 y offset; probado con protocolo overlay |
| Alineación por tramos | Implementada conservadoramente | Tests sintéticos de velocidades y cortes; éxito musical general no demostrado |
| Pronunciación local | Implementada | eSpeak NG/langid y pykakasi; ejemplos y tests, calidad aproximada |
| Vista dual | Implementada | Slots text/translation separados; render offscreen sin solapamiento |
| CrisperWhisper2.0 | Integrado en código | Runtime/modelo NO instalados: descarga torch falló por DNS |
| Tiempos ASR por palabra | Implementados |98 tests disponibles pasan, incluidos audio→palabra→overlay; modelo sustituido en pruebas |
| Crisper GPU RX590 | Pendiente | Ruta C++/Vulkan investigada y receta de compilación experimental, no compilada/probada |
| Push GitHub | Pendiente por red | No asumir que el commit local está publicado |
| Compositor Wayland/X11 | Validación final pendiente | Preview offscreen no demuestra blur real ni toda experiencia desktop |

## 4. Arranque e instalación

Python principal: `.venv/bin/python`; sistema Python3.14 y Qt/PyQt6 deben coincidir
con LayerShellQt de Kotonoha. Instalación editable, icono SingLayer.desktop ejecuta
`singlayer app`. `singlayer start` es el modo heredado, no el panel moderno.

```sh
bash scripts/setup.sh
bash scripts/setup-recognizer.sh
bash scripts/setup-crisper.sh
.venv/bin/singlayer app
```

Setup base instala engines y runtime reconocimiento; Crisper es setup explícito
adicional porque requiere descarga y conversión de pesos. Dependencias sistema:
uv, Qt/PyQt6 compatible, pactl/parec, FFmpeg. Submódulos inicializados por setup:
Kotonoha y WebNowPlaying; SongRec/SyncLyrics son referencias/opcionales.

WebNowPlaying oficial necesita custom adapter local puerto8975. Bridge de SingLayer
es la fuente de reloj/pista, no MPRIS del escritorio como selección automática.
Perfil overlay gestionado en `~/.config/singlayer/managed/kotonoha/config.json`,
con adapter local28746 y traducción habilitada para vista dual. Preserva otros
ajustes. Kotonoha tiene lock de instancia: reiniciar solo procesos propios.

## 5. Arquitectura y contratos

- bridge.py/state.py: WNP revisión3, HTTP `/status` APIv2, `/cover?rev=...`, puerto8975.
  Portada binaria uint32LE+PNG/JPEG. No identificar Brave fiablemente por nombre
  genérico Chromium. No leer otras pestañas privadas para resolver metadatos.
- dashboard.py: Qt, polling700ms, QProcess, epochs por búsqueda/guía/ASR, portada,
  multilinea, sincronización manual, variantes, cache de sesión letras32/guías16.
  Descarta resultados de pistas anteriores. Inicia servicio Crisper propio cuando
  búsqueda termina sin letra o hay edición/candidatos múltiples y playback activo.
- workflow.py:4 operaciones concurrentes máximo, nativos primero/extras después,
  hasta4 interpretaciones normalizadas del título, metadata/reconocimiento en
  paralelo. SoundCloud no acepta uploader como prueba de artista. Dos recording
  IDs iguales corroboran; un reconocimiento aislado queda etiquetado candidato.
- worker.py: procesos aislados, timeouts, cancelación y reap. SongRec prioritario;
  fallback `scripts/recognize_audio.py` en `.build/recognizer` Python3.12 ShazamIO0.8.1.
  Prueba importación antes de capturar. Nunca salta a música futura para reconocer.
- browser_audio.py: pactl sink-input navegador, `parec --monitor-stream=<id>` y su
  monitor. Ambigüedad rechazada, nunca default monitor/micrófono. Un flujo Chromium
  puede mezclar varias pestañas: aislamiento por pestaña no garantizado.
- audio_meter.py: FFT1024; buffers cortos. artwork.py: URLs/CDN verificadas, binario
  bridge prioritario. diagnostics.py: log rotativo128KiB+1backup, sin letras/audio.
- overlay_link.py: adapter Kotonoha28746; reloj y documentos source-neutral;
  transforma línea y palabras para ajuste manual. Pronunciación dual usa translation.
- alignment.py: calibración dos puntos y comparación1–3 líneas mediante similitud
  >=.82 y margen frente a rivales. Rechaza frases cortas/estribillos indistinguibles;
  CJK por caracteres. Cambia solo tramos observados, no extrapola cortes futuros.
  Tiempos por palabra Crisper se conservan solo en coincidencia exacta de1 línea.
- pronunciation/local.py: langid detecta idioma por línea/contexto, eSpeak NG en/fr/
  de/it/pt/ru, japonés pykakasi; español intacto; otros idiomas original con aviso.
  Deduplica texto. __init__.py generate usa local; generate_remote ChatJimmy
  permanece como código heredado/testeado, no usado por UI. No envíos de letras
  para pronunciación. No guía fonética aplicada a documento live estimado todavía.

## 6. CrisperWhisper actual

Se retiró la invocación whisper.cpp/servidor28747 del panel. Sus `.build/` antiguos
solo son historia. **No cargar un modelo Crisper en stock whisper.cpp:** cambia
vocabulario/control IDs y requiere compatibilidad del runtime.

Servicio `crisper_service.py`, loopback127.0.0.1:28748, identidad
singlayer-crisperwhisper, health con device=cpu. Modelo persistente, una inferencia
a la vez, WAV mono16kHz PCM16 <=30s/1MB, sin grabación guardada. Panel usa
scripts/run-crisper.sh y log `.build/crisper-server.log`. Descargas fuera de playback.

Runtime aislado `.build/crisper-runtime`, Python3.12; CrisperWhisper2.0.3,
ctranslate2-crisperwhisper4.7.1.post3. No mezclar upstream ctranslate2 que pisa el
mismo módulo. PyTorch CPU+Transformers solo para convertir modelo oficial
nyralabs/CrisperWhisper2.0_small a CT2 int8. Model revision resuelta y fijada en
`.build/crisperwhisper/model-lock.json`; ready.json se publica solo tras carga.
**Ahora no existe ready.json:** setup falló al descargar torch; no afirmar instalado.

API transcribe por defecto fuerza inglés: servicio llama detector acústico de CT2
mediante `_engine` (seam privada de versión fijada), después transcribe con idioma,
sr16000, verbatim y word_timestamps=True. Revalidar seam al actualizar upstream.
Palabras Crisper están strip; adaptador restaura separadores por idioma y conserva
CJK sin espacios. No redistribuye tiempos ni fabrica timings futuros.

live_transcription.py: ventanas12s/hop8s, cola1, captura e inferencia independientes;
ancla a posición browser al capturar, invalida por pausa/seek/pista/deriva/flujo.
Silencio RMS filtrado (NO separación vocal). Segmentos fuera de ventana se descartan
y se continúa. Procesos/tareas se cancelan y recogen. Tiempo HTTP90s CPU; cola acotada
impide acumulación ilimitada pero CPU lenta sigue generando retraso. Primer playback
no puede anticipar letra futura; no hay cache acústica persistente para replay.

## 7. GPU/C++: trabajo preciso para continuar

Ver docs/GPU.md y scripts/build-crisper-vulkan.sh. Revisados CMake y fuente del
community Saganaki22/CrisperWhisper.cpp, no solo README: usa dependencia whisper.cpp
080bbbe85230f624f0b52127f1ae1218247989f9 con patch cross-attention; CMake no fuerza
Vulkan OFF; contextos de inferencia/timing pasan use_gpu/device. Es ruta plausible,
no garantía. Paquetes publicados solo CPU/CUDA. La CLI por ventana recarga modelo:
no conectar eso como solución final live sin servidor C++ persistente.

Receta experimental v1.2.0: CUDA OFF, GGML_VULKAN ON, exige target real ggml-vulkan,
pruebas nativas. Solo sintaxis comprobada: sin red para clonar/compilar y sin GPU
expuesta. No instala pesos ni activa panel. Necesita CMake, C++17, shaderc/glslc,
Vulkan loader/headers, SPIRV headers; puede reutilizar headers locales antiguos.

Con acceso real: compilar, fijar SHA upstream resuelta, descargar modelo GGML small
con metadata sidecar/revisión/hash, probar audio autorizado con word timestamps.
Comprobar logs Vulkan tanto inferencia como alignment, timings válidos, CPU/GPU
latencia/memoria, idiomas y singing. Desactivar flash attention inicialmente si
Polaris lo requiere. Si funciona, servicio C++ persistente con idioma detectado y
contrato28748, health backend real y cancelación; solo entonces activar GPU por
defecto. No añadir un modo “GPU” que silenciosamente ejecute CPU.

Hardware identificado antes con acceso completo: RX590 GME RADV POLARIS10,
Mesa26.1.8, PCI1002:6fdf, fp16=false. PCI genérico RX5802048SP. Benchmark antiguo
Whisper base11s voz JFK: CPU4.206/4.275/4.256s, Vulkan1.584/1.007/1.036s,
texto igual, log Vulkan0. **No prueba Crisper ni precisión de canto.**

## 8. Evidencia real anterior

- `docs/search-evaluation.json`:5 títulos/URLs SoundCloud (Night Changes,
  NIGHT DANCER, Them Changes y After Dark) con ediciones sped/slowed/pitched/reverb/
  muffled, catálogo LRCLIB encontrado. Un registro After Dark invertía artista y
  título; preservar candidatos y validar audio. No se publican letras/audio.
- Live anterior NIGHT DANCER con motor viejo:2 eventos5 líneas, lag1.11/1.35s
  respecto al fin del segmento; captura12s se añade. No atribuir ese resultado a
  CrisperWhisper. After Dark slowed descubrió tiempos inválidos; recuperación
  probada offline, no repetida real después ni con Crisper.
- ChatJimmy omitía palabras en ejemplos reales; sustituido por guía local. Español
  original intacto; inglés/francés por diccionario; kanji/idioma ambiguos siguen
  requiriendo revisión humana. No estudio de precisión lingüística exhaustivo.
- docs/bilingual-preview.png: render real offscreen original+guía en slots distintos.
  No screenshot compositor ni validación completa de Wayland/X11.

## 9. Validación y límites del entorno

Última prueba: **98 passed,4 deselected**, Ruff/sintaxis shell/git diff check OK.
Cuatro tests exigen IPC real y fallan con PermissionError en este sandbox:
websocket_to_real, web_page_origins, control_rejection,
upstream_reads_browser_track_and_clock. No borrarlos ni convertirlos en mocks.

```sh
.venv/bin/ruff check src tests scripts/prepare-crisper.py
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
# Solo si IPC está bloqueado:
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q -k 'not websocket_to_real and not web_page_origins and not control_rejection and not upstream_reads_browser_track_and_clock'
bash -n scripts/*.sh
```

Estado actual: sandbox workspace-write, red restringida, aprobación never. Paths
del workspace escribibles; sockets y D-Bus denegados, /dev/dri ausente. GitHub/PyPI/
PyTorch no resuelven DNS. Acceso adicional solicitado no concedido. No enviar
sandbox_permissions. Recomprobar estos límites al cambiar de sesión; antes sí hubo
GPU/red/audio disponibles. Herramienta web de consulta puede leer fuentes, eso no
implica que git/uv tengan conexión.

Pestaña de prueba Brave anterior id1970334636 browser3 con After Dark slowed;
CUA no pudo recuperarla por error request-header policy. No afirmar que se pausó
ni cerró. Comprobar estado antes de actuar; no cambiar otras pestañas del usuario.

## 10. Licencias, datos y siguientes tareas

SingLayer integración MIT; dependencias retienen licencias. Crisper código MIT,
pesos2.0 bajo Nyra Health Non-Commercial Research License. Community conversión no
cambia la licencia. eSpeak NG y pykakasi GPL3; langid BSD; SongRec GPL3 proceso
separado; SyncLyrics MIT+Commons Clause referencia, no runtime. Ver THIRD_PARTY.md.
Modelos/medios/letras completas/caches/secretos no se incluyen en Git.

Prioridad:
1. Restaurar acceso real; completar push sin force y verificar remoto.
2. Ejecutar receta C++ Vulkan y gate descrito; resolver AMD antes de llamar listo.
3. Instalar runtime/modelo Crisper CPU si se necesita baseline y comparar precisión.
4. Servicio C++ persistente si pasa Vulkan; no CLI nueva carga cada8s.
5. Validación audio sped/slowed/reverb/cortes, IPC completo, compositor y UI actual.
6. Falta guía fonética en live, replay/cache de tramos, y referencia de audio original
   opcional. Shazam no entrega original, no fingir matching de referencia inexistente.

No modificar upstream/kotonoha sin leer su AGENTS.md. Submódulos actuales:
Kotonoha175cfcc, WebNowPlaying764878b, SongRecb94ee61, SyncLyrics6128192;
no se cambiaron. Reinicios solo procesos propios, no pkill genérico.
