# Letras progresivas y menor espera — 2026-10-04

El panel ya entrega las letras de cada fragmento, sin esperar a terminar toda la pista. Empieza cerca del segundo que se está reproduciendo, con margen para el tiempo de inferencia; después prepara lo que falta. Consulta el reloj real entre fragmentos para respetar saltos y pausas. Todos los fragmentos de la grabación siguen cubiertos, incluido el final.

La descarga reutiliza la extracción de metadatos de yt-dlp, en lugar de pedir al sitio la misma información por segunda vez. La descarga y la decodificación pueden avanzar mientras el motor se prepara. Los resultados completos de la versión exacta se consultan en disco antes de cualquier petición web o inferencia, con identidad del motor/modelo y comprobación de título y duración. Se reutiliza la transcripción acústica al cambiar el catálogo o la fuente de letra, sin volver a analizar el audio.

En selección automática, la pista completa puede usar Whisper Vulkan instalado aunque no se encuentre catálogo. Elegir CrisperWhisper CPU explícitamente conserva esa elección. Se mantienen el modelo large-v3-turbo Q5_0 y los filtros de confianza; no se ha reducido el modelo para aparentar mayor rapidez. El servidor instalado utiliza decodificación greedy; las opciones están documentadas en el [servidor oficial de whisper.cpp](https://github.com/ggml-org/whisper.cpp/blob/master/examples/server/README.md).

## Prueba real con Night Changes sped up

Enlace: https://soundcloud.com/kaja_roblox-cz/night-changes-sped-up

| Medida | Resultado |
|---|---|
| Primera entrega anterior | Al finalizar todo el análisis: 145,24 s en la prueba anterior |
| Primera entrega progresiva | 19,750 s: 6 frases, tiempos entre 64,22 y 85,72 s |
| Segundo simulado de reproducción al recibirlas | 67,75 s: los tiempos incluían ese momento |
| Descarga y decodificación | 7,59 s hasta comenzar inferencia |
| Pista cubierta | 177,3405625 s, 11 fragmentos y 42 líneas finales |
| Análisis completo de esta nueva prueba | 150,016 s: el motor no terminó antes; la mejora principal es la entrega temprana |
| Repetición desde caché local | 0,1998 s, sin red, descarga ni inferencia |

Las dos mediciones completas son ejecuciones distintas; no constituyen un benchmark estadístico. Los tiempos dependen de la red, el motor, la voz y la carga del equipo. No son una promesa de veinte segundos para cualquier canción ni una medida de exactitud contra transcripción humana.

También se probó una variante de 30 segundos/avance24: primera entrega25,514 s y resultado final135,319 s/38 líneas. Se descartó para esta entrega por empeorar la espera inicial y cambiar los resultados. Se conservan ventanas24/avance16.

YouTube conserva la descarga completa tras eliminar la doble extracción: 240,2104375 s decodificados; extracción3,183 s, descarga/decodificación4,256 s. No se ejecutó ASR completo sobre esa segunda pista en esta tanda.

## Caché y límites

Hasta16 resultados, reutilizables durante24 horas, en `~/.cache/singlayer/full-track` o bajo `XDG_CACHE_HOME`. El audio descargado sigue siendo temporal y se elimina. Cambiar la versión o el modelo no hereda tiempos de otra grabación. Solo el resultado completo se guarda como caché reutilizable; un resultado parcial se presenta como análisis progresivo. Si se cancela o falla, no se declara terminada la pista.

Para una pista nueva hace falta descargar y analizar al menos un fragmento. La primera escucha todavía puede tener espera; una introducción instrumental no produce letras hasta que se detecte voz fiable. Los fragmentos futuros que faltan no se inventan. Las transcripciones y sus tiempos siguen siendo estimados.

209 pruebas pasan. Incluyen entrega parcial antes del resultado final, cobertura completa al cambiar el orden de análisis, presentación en el panel antes de finalizar, caché sin red/inferencia, rechazo de versión/modelo distintos, reloj real con seek/pausa y respeto de la elección explícita de CPU. Ruff y diff check pasan.

Actualización posterior: el motor ahora evita codificación duplicada y reduce también el análisis completo; medidas y límites en [ENCODER_REUSE.md](ENCODER_REUSE.md).
