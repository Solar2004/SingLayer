# Sincronización automática y GPU — 2026-10-04

SingLayer construye una línea de tiempo con inicio y final de cada frase. La vista
**≡** muestra esos segundos y sigue el reloj del navegador. Los tiempos se limitan
a la duración real de la canción; un ajuste de letras nunca cambia el reproductor.

## Cómo se calcula

1. Captura exclusivamente el navegador seleccionado (PulseAudio o PipeWire).
2. Whisper.cpp large-v3-turbo Q5_0 permanece cargado en la RX590 mediante Vulkan.
   Ventanas24s, avance16s y una sola ventana pendiente evitan acumular grabaciones.
3. DTW aporta centros acústicos de tokens. Su envolvente establece tiempos
   **estimados por línea**, excluyendo el silencio inicial. No se presentan como
   límites exactos de palabras. Canto/efectos difíciles pueden producir errores.
4. El texto se contrasta con LRCLIB/Kotonoha. Las coincidencias inequívocas alinean
   tramos observados. Los estribillos repetidos solos no establecen un reloj.
5. Tres o más referencias textuales únicas, separadas al menos15s y coherentes
   dentro de750ms, permiten estimar velocidad y desfase del catálogo completo.
   Una referencia posterior contradictoria invalida ese reloj. Las versiones
   marcadas remix/mashup/loop/cut/snippet permanecen en alineación por tramos.

El reloj completo es una predicción de velocidad constante: no demuestra que un
upload sin esas etiquetas carezca de cortes futuros. Se muestra como estimado.
La primera reproducción necesita escuchar varios fragmentos antes de reunir las
referencias. No puede anticipar una voz aún no capturada sin un catálogo y reloj.

Los fragmentos medidos se conservan en RAM (16 grabaciones,512 líneas por documento)
para retroceder y repetir sin borrar tiempos ya observados. Los ajustes manuales
se guardan para32 combinaciones exactas de grabación/catálogo; no se guardan audio
ni letras en esa preferencia. La guía fonética local funciona también con audio
transcrito y con el reloj automático. Otra letra no hereda una guía anterior.

## Instalación reproducible y selección

```sh
bash scripts/setup-whisper-vulkan.sh
.venv/bin/singlayer app
```

El script exige un checkout limpio fijado de whisper.cpp, compila Vulkan, verifica
SHA256 del modelo y ejecuta inferencia real. Solo publica ready.json si el log
confirma `using Vulkan0 backend` y el fixture de voz produce transcripción.
El servicio vuelve a comprobar uso real de Vulkan al iniciar: falla explícitamente
si no existe, en lugar de presentar CPU como GPU. Descarga durante instalación,
no durante reproducción. No modifica drivers. Cerrar la ventana termina los
procesos propios; el hijo nativo está ligado a la vida del servicio en Linux.

El usuario autorizó esta alternativa después de comprobar limitaciones del modelo
Crisper small y el404 de la ruta C++ comunitaria. Crisper CPU permanece instalado:

```sh
SINGLAYER_ENGINE=crisper .venv/bin/singlayer app
```

Sin Whisper ready.json se selecciona Crisper CPU explícitamente. Ambos usan el
contrato local `singlayer-transcription`, puerto28748 y WAV mono PCM16/16kHz,
<=1MB/30s, una inferencia a la vez. El proceso nativo de Whisper usa un puerto
loopback efímero propio. Las peticiones de navegador con Origin al adaptador se
rechazan; la grabación no se sube a un servicio ASR externo.

Pins:
- whisper.cpp: `60c0be6ac8fa71b1a2ae2dd938a31a34a508e774`, MIT.
- ggerganov/whisper.cpp: revisión `5359861c739e955e79d9a303bcbc70fb988958b1`.
- `ggml-large-v3-turbo-q5_0.bin`,574041195bytes.
- SHA256: `394221709cd5ad1f40c46e6031ca61bce88931e6e088c188294c6d5a55ffa7e2`.

## Evidencia real

- RX590 GME, RADV POLARIS10; inferencia y DTW con backend Vulkan0 confirmado.
- Night Changes sped up: dos ventanas reales56–80s y64–88s; seis líneas por
  ventana y tres líneas alineadas por fragmento. Cinco referencias acumuladas
  dieron velocidad **1.23305588585** y desfase **2.84205707491s** automáticamente.
- Referencia reservada, no usada al calcular ese reloj: estribillo en otro
  fragmento40–64s. Inicio previsto40.02085s; DTW observado40.24s: diferencia
  **0.219s**. Es consistencia contra DTW, no anotación humana ni exactitud universal.
- Night Dancer sped up japonés: API real detectó japonés, transcribió dos líneas
  y alineó tres líneas del catálogo; primera voz situada en82.68s en lugar de
  asignarle el silencio desde70s. Variante de segmentación previa: tres líneas
  transcritas y una alineada. No se presume que cada ejecución segmente igual.
- Pronunciación local real: seis guías inglesas y dos japonesas, sin cambiar tiempos.
- 24s de canto requieren aproximadamente11–16s de inferencia en esta RX590.
  Captura24s añade espera inicial; no es latencia total de11s.
- X11: renderer nativo ejecutado y revisado. Wayland: compositor KWin de prueba,
  layer shell activo y prueba de ciclos de blur aprobada. No prueba apariencia en
  cada compositor/configuración del usuario.
- Apagado controlado del adaptador comprobó que el proceso GPU hijo se detuvo.
- 160 pruebas completas, Ruff, shell y diff check pasan.

After Dark muy muffled y Honeypie slowed/reverb siguieron produciendo resultados
incompletos en las muestras adicionales. Se conserva corrección manual y estado
incierto. Shazam había acertado10/10 muestras de la matriz anterior; eso prueba
identidad en ellas, no sincronización universal. No se comprometen medios/letras.

## Artista ausente, recortes y símbolos

Sin artista, la letra de metadatos queda candidata mientras Shazam intenta
corroborar título/artista con dos muestras coincidentes. Si falla, no se inventa
identidad. SoundCloud, identidad reconocida, artista ausente y catálogos con
frases fuera de la duración del upload activan comprobación acústica.

El reloj usa la posición del fragmento reproducido, no exige escuchar desde el
principio. Tres referencias pueden mapear un recorte desde el segundo90 del
original al segundo2 del upload. Si un estribillo repetido no identifica su
ocurrencia, se muestra la transcripción medida sin asignarle una posición original
inventada. El avance del navegador dentro de una canción completa conserva su
propio reloj; un upload recortado necesita estimar el desfase.

La comparación normaliza Unicode decorativo, puntuación, apóstrofos tipográficos
y caracteres invisibles dentro de palabras, conservando la letra visible. Esto
no garantiza reconocer audio inaudible o cualquier escritura arbitraria.

Regresiones específicas y puerta completa:160 pruebas, Ruff y diff check pasan.

## Contexto de estribillos y cambios de sección

Un estribillo repetido puede alinearse cuando dos frases únicas de la misma
ventana lo rodean, están separadas al menos15s y forman un reloj coherente. Solo
se acepta una ocurrencia dentro de1.5s del tiempo previsto y con texto compatible.
Sin ese contexto se mantiene la transcripción medida. No se usa el reloj antiguo
para elegir un estribillo después de un corte.

Una nueva referencia única incompatible con el reloj establecido lo invalida y
vacía las referencias antiguas. La nueva sección requiere nuevamente tres
referencias para estimar su velocidad/desfase. Durante esa espera se muestran
tramos medidos. Detección posterior al reconocimiento, no anticipación del corte.

Pruebas de regresión: repetición con/sin contexto, contexto roto por corte,
invalidez del reloj anterior y reconstrucción con referencias nuevas. Puerta
completa:160 pruebas. No se ha medido esta mejora contra anotaciones humanas de
una nueva matriz de remixes reales.

## Corrección de letra que desaparecía al finalizar

Una ventana acústica retrasada no sustituye la letra completa si sus frases ya
pasaron en el reproductor. Se mantiene el catálogo candidato mientras Whisper
reúne referencias. Se usan los tramos medidos al reproducir su intervalo y el
reloj completo cuando está calibrado. Sin catálogo, se conserva la transcripción
con su limitación de retraso. Mantener el catálogo no demuestra que sus tiempos
sean correctos: la comprobación acústica continúa.

Regresión de UI: búsqueda terminada, fragmento atrasado, conservación de letra
actual/completa, seek hacia tramo medido y regreso al catálogo.160 pruebas pasan.

## Elección de letra y motor

En ⋯ Ajustes, «Qué letra mostrar» permite Automático, Solo letra del catálogo o
Solo transcripción del audio. Transcripción muestra las palabras acústicas sin
corregirlas con el catálogo ni aplicar su velocidad/desfase. Necesita captura e
inferencia; un texto observado pasado no se convierte en una frase futura.

«Motor de transcripción local» permite automático, Whisper.cpp GPU Vulkan o
CrisperWhisper CPU. La selección se guarda. Cambiar motor detiene los procesos
propios, espera a que el servicio libere su puerto y limpia transcripciones,
caché y referencias del motor anterior. Whisper explícito sin instalación válida
falla con mensaje, no cambia silenciosamente a CPU. Crisper CPU está instalado
pero sus resultados de canto pueden ser peores; no se presenta como GPU.

Regresiones: texto acústico directo con catálogo disponible, cambio a catálogo,
persistencia de elección y limpieza al cambiar motor.160 pruebas completas pasan.

## Catálogo candidato e instrumental

Esta regla reemplaza la conservación anterior del catálogo en la vista activa:
la lista ≡ conserva la letra candidata, pero en automático el overlay y la frase
actual requieren tramos alineados al audio o un reloj acústico calibrado. Una
búsqueda exitosa no es evidencia de voz. Todas las pistas en automático activan
contraste acústico. «Solo catálogo» sigue siendo una elección explícita que no
verifica el audio.

Ventanas sin palabras fiables/silencio invalidan el reloj. El adaptador Whisper
rechaza puntuación sola, etiquetas Music/Instrumental y segmentos con
avg_logprob inferior a−1. Reproceso de resultados nativos reales: After Dark que
solo devolvió «…» ahora produce cero líneas; Night Dancer japonés conserva tres.
No se garantiza detectar todas las alucinaciones con texto plausible.

Se evaluó Silero VAD6.2.0 a umbrales0.5 y0.1: descartó también canto japonés real.
NO se activó esa dependencia en producción ni se filtró todo canto como silencio.
El modelo y herramienta experimental permanecen locales; el instalador no los
requiere. Evidencia de regresión y puerta completa:160 pruebas, Ruff/diff OK.

## Flujo de autoridad de la letra

1. Identidad: metadatos aportan candidatos; durante reproducción se espera la
   corroboración acústica de Shazam. Dos muestras concordantes confirman su
   identificación, no el texto ni los tiempos. Una sola queda incierta.
2. Versión de velocidad constante, incluido sped up/slowed: comparar frases
   acústicas únicas con catálogo, estimar velocidad/desfase con tres referencias
   coherentes y mostrar el reloj estimado. Los cortes invalidan y reconstruyen.
3. Remix/mashup/bootleg/medley/loop/cut/snippet/excerpt/best part: en Automático
   seleccionar Whisper Vulkan y mostrar directamente su transcripción/tiempos.
   No se sustituye el texto por el catálogo ni se aplican sus ajustes manuales.
4. Sin palabras fiables: no presentar el catálogo candidato como voz observada;
   conservarlo en la lista para revisión. Los motores aún pueden alucinar texto.

La clasificación inicial usa etiquetas del título; un remix no etiquetado no
puede darse por detectado de antemano. «Solo transcripción» permite indicarlo
manualmente. Los modos explícitos catálogo/transcripción y selección de motor
siguen disponibles. En Automático, la ruta remix exige Whisper instalado y no
lo cambia silenciosamente por Crisper. Al cambiar de ruta se selecciona el
servicio propio correspondiente y se separan cachés por motor/ruta.

Regresiones: límites de palabras (Cutting Crew/Sloop no son cuts/loops), speed
up sigue alineación, títulos remix eligen Whisper, texto remix no heredado del
catálogo, sin ajustes de reloj original, elecciones explícitas preservadas y
Shazam corroborado antes de devolver una letra confirmada.160 pruebas pasan.

Este flujo ordena evidencias; no garantiza toda música perfecta ni texto futuro
antes de capturar voz. Un remix usa audio real, pero mantiene retraso y posibles
errores ASR. No se hizo una nueva matriz de remixes reales en este cambio.
