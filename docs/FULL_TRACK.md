# Análisis de pista completa — 2026-10-04

Con la [extensión de enlace automático](AUTOMATIC_SOURCE.md) cargada, SoundCloud y YouTube inician el análisis completo por pista sin pegar enlaces. Sin ella, usa el método manual siguiente.

En **⋯ Ajustes → Analizar pista completa desde enlace**, pega el enlace exacto de la versión abierta en el navegador. El panel comprueba título y duración, descarga el audio completo, lo decodifica y analiza ventanas de 24 segundos con avance de 16 segundos, incluyendo el final. Los tiempos resultantes siguen la posición del reproductor al avanzar o retroceder. No se sustituye un remix por una búsqueda de la versión original.

Se utiliza el motor seleccionado: Whisper.cpp Vulkan o CrisperWhisper CPU. En automático, los remixes conservan el texto acústico; para canciones normales solo se reemplaza texto por catálogo cuando existe una coincidencia única suficientemente fuerte. Se conservan los tiempos medidos. Puedes elegir solo transcripción para mostrar el texto acústico original.

El audio temporal se elimina al terminar o cancelar. Se guardan hasta 16 resultados de transcripción y tiempos en `~/.cache/singlayer/full-track` (o bajo `XDG_CACHE_HOME`); borra esa carpeta para eliminarlos. Cambiar de pista cancela el trabajo pendiente. El botón **Cancelar análisis completo** detiene el proceso de descarga/análisis.

## Límites

- Enlaces HTTPS públicos de YouTube, SoundCloud, Bandcamp, Vimeo, Mixcloud, Dailymotion y Audiomack; pista individual, hasta 15 minutos y 100 MB. No se ha probado cada servicio.
- `yt-dlp[default]==2026.8.19` y FFmpeg; YouTube se probó con Node 24.15.0 como runtime JavaScript. El analizador usa Node cuando está disponible en PATH.
- Sin cookies del navegador: acceso restringido, login o descargas bloqueadas producen un error. Se comprueba la duración decodificada para rechazar previews o descargas incompletas.
- WebNowPlaying no entrega la URL de la página: la extensión propia aporta el enlace exacto. Sin ella, hay que pegarlo manualmente. La lectura de Brave volvió a funcionar, pero la herramienta bloqueó su página de extensiones; la instalación debe completarse manualmente una vez.
- Puede tardar varios minutos. Transcripción y tiempos acústicos son estimados: voces muy alteradas e instrumentales todavía pueden producir errores. No se garantiza sincronización perfecta.

## Pruebas reales

| Prueba | Resultado |
|---|---|
| [SoundCloud: Night Changes sped up](https://soundcloud.com/kaja_roblox-cz/night-changes-sped-up) | Audio completo 177,3405625 s; 11 ventanas; 42 líneas; última frase termina en 175,9005625 s; 5 coincidencias únicas con catálogo; descarga + Whisper Vulkan en 145,24 s |
| Repetir SoundCloud | Caché en 1,7 s; sin nueva descarga ni inferencia |
| Panel Qt + protocolo del overlay | Resultado real aceptado: 42 líneas, fuente `full-audio`; navegación por tiempos y seek verificados |
| [YouTube: One Direction - Night Changes](https://www.youtube.com/watch?v=syFZfO_wfMQ) | Descarga y decodificación completas: 240,2104375 s, archivo 4.019.932 bytes. No se ejecutó ASR completo sobre esta segunda pista |

188 pruebas pasan, incluidos rechazo de pista equivocada, cobertura del último segundo, conservación de tiempos, remix sin sustitución de texto, resultado vacío, cancelación con limpieza del proceso y reproducción de la línea de tiempo completa. Ruff y `git diff --check` pasan. No se distribuyen audio ni letras completas de estas canciones.
