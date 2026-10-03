# SingLayer

Un panel nativo para cantar sobre la música de tu navegador, reutilizando
WebNowPlaying, Kotonoha, SongRec/ShazamIO y syncedlyrics.

![Panel real, sin canción conectada](docs/dashboard-preview.png)

## Abrir

Si ya tenías SingLayer abierto, cierra la versión anterior (incluido cualquier
`singlayer start` de una terminal). Abre SingLayer desde el menú de aplicaciones.
El lanzador existente apunta al mismo código y no necesita reinstalarse.

Para una instalación nueva consulta las dependencias Qt en el [README](README.md):

```sh
git clone https://github.com/Solar2004/SingLayer.git
cd SingLayer
bash scripts/setup.sh --engines
.venv/bin/singlayer app
```

El panel también ofrece **Instalar motores** cuando faltan ShazamIO, syncedlyrics
o NumPy. Usa `uv` y PyPI, sin sudo. Necesita conexión a Internet. FFmpeg y `parec`
son dependencias del sistema para reconocer audio y mostrar el espectro; no se
instalan automáticamente. SongRec es opcional: si existe se usa como proceso
separado, y si no se utiliza ShazamIO.

## Navegador y controles

Instala [WebNowPlaying](https://chromewebstore.google.com/detail/webnowplaying/jfakgfcdgpghbbefmdfjkbdlibjgnbli),
crea un adaptador personalizado con puerto **8975** y actívalo. Desactiva
**Use desktop players** para evitar que nuestro MPRIS vuelva a entrar en la
extensión. Recarga SoundCloud después de instalarla y reproduce una canción.

- **Conectar** inicia el puente y busca letras de la canción recibida.
- **Letras** abre o cierra el overlay Kotonoha.
- **Buscar** corrige canción/artista y vuelve a consultar los proveedores.
- **Shazam** solicita reconocimiento de audio, con permiso y reproducción activa.
- **Sincronizar** permite hacer doble clic en la línea que estás cantando.
- **Desfase / Velocidad** ajustan la letra, nunca la reproducción del navegador.
- **■** detiene solamente los procesos iniciados por esta ventana.

La portada llega como imagen binaria desde la extensión; no se descargan URLs
arbitrarias de las páginas. Si no hay portada, se muestra un marcador neutro.
Los iconos vienen del tema del sistema. WebNowPlaying no diferencia de forma
fiable Brave/Chrome/Vivaldi: el selector permite indicar la marca manualmente.
El botón de extensión se oculta cuando hay conexión. Sin conexión se ofrece
instalar/configurar, **no se afirma que la extensión esté desinstalada**.

## Búsqueda paralela

LRCLIB, NetEase y KuGou se consultan mediante el código existente de Kotonoha.
Si no encuentran letras, syncedlyrics aporta Musixmatch y Megalobiz. Genius queda
como alternativa de texto sin tiempos, visible en el panel, no como karaoke falso.

Con **Audio del sistema** activado, el primer reconocimiento puede solaparse con
la búsqueda. Hay un máximo de cuatro operaciones simultáneas y tres fragmentos
de 12 segundos por búsqueda; los fragmentos se capturan en secuencia. Al obtener
letras se cancela el trabajo sobrante. Pausar audio durante ese flujo, cambiar
de pista, detener o cerrar cancela la búsqueda y sus procesos. Las consultas de
la misma identidad se comparten; se conservan hasta 32 resultados en memoria
durante la sesión. Cada operación tiene tiempo límite y hay un límite global.

Los puntos de progreso distinguen búsqueda activa, resultado, ausencia,
dependencia faltante, error y operación omitida. «Letra encontrada» **no prueba**
que sea la versión correcta o esté sincronizada con un remix.

## Audio y privacidad

La captura está apagada al abrir la app. **Audio del sistema** utiliza el monitor
de salida de PulseAudio/PipeWire, nunca el micrófono. Incluye cualquier sonido
que salga por esa salida, no únicamente SoundCloud: evita llamadas u otro audio
privado durante el reconocimiento. Shazam recibe huellas de audio; los proveedores
de letras reciben canción y artista. Los fragmentos no se conservan: con SongRec
el WAV temporal se elimina al acabar; con ShazamIO se entrega en memoria.
Las barras son un espectro FFT real, no una animación aleatoria.

## Compatibilidad y límites comprobados

El panel aplica glow local y título personalizado. Reutiliza el blur nativo de
Kotonoha en Wayland cuando el compositor lo admite; en X11 y sin esa capacidad
queda el fondo oscuro translúcido. El blur nuevo no se ha validado en vivo.

El panel usa un perfil de overlay separado (`singlayer/managed`) y el protocolo
de Kotonoha en **28746**, con entrada `adapter` exclusivamente: no elige otro
MPRIS a espaldas del panel. El antiguo comando `singlayer start` permanece como
modo heredado y no incluye este flujo de búsqueda.

Se probaron localmente la interfaz, el coordinador paralelo, los límites de
procesos, la FFT y la recepción real del protocolo por Kotonoha. La instalación
de ShazamIO/syncedlyrics y la prueba en vivo siguen pendientes: esta sesión de
desarrollo no puede resolver PyPI ni acceder al audio/D-Bus del escritorio.
No se promete encontrar todas las canciones ni sincronizar automáticamente
remixes, recortes o cambios de velocidad. La cola/siguiente canción sigue pendiente.

Créditos y licencias: [THIRD_PARTY.md](THIRD_PARTY.md).
