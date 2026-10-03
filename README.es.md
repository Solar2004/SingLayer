# SingLayer

Unimos componentes existentes para cantar sobre la música de tu navegador:

**WebNowPlaying → conector SingLayer → Kotonoha → letras sincronizadas.**

La extensión, la búsqueda de letras, las animaciones y el overlay son proyectos
existentes. El código nuevo conecta sus interfaces. No hace falta reproducir la
música dentro de otra aplicación.

## Primera versión

- Conector con canción, artista, posición, pausa, cambio de pista y varios navegadores.
- Controles de reproducción con confirmación del navegador.
- Overlay Kotonoha con tres líneas, brillo suave y búsqueda manual de letras.
- Compilado con Qt del sistema. Render comprobado en X11 y KWin Wayland aislado.
- SongRec y SyncLyrics clonados como referencias; reconocimiento automático y
  detección de la siguiente canción **todavía pendientes**.
- Pruebas del protocolo realizadas; aún falta probar la extensión con música real
  de SoundCloud/Spotify/YouTube en Brave/Vivaldi.

## Arranque

Consulta primero las dependencias del sistema en el [README principal](README.md).

```sh
git clone https://github.com/Solar2004/SingLayer.git
cd SingLayer
bash scripts/setup.sh
.venv/bin/singlayer start
```

Instala la extensión oficial [WebNowPlaying](https://chromewebstore.google.com/detail/webnowplaying/jfakgfcdgpghbbefmdfjkbdlibjgnbli)
en tu navegador. En sus ajustes añade un adaptador personalizado con puerto **8975**
y actívalo. Desactiva «Use desktop players» para evitar un bucle con nuestro reproductor MPRIS.

Reproduce una canción. La lupa del overlay permite elegir otras letras y las flechas
ajustan su sincronización. El resaltado por palabra depende de que existan tiempos
por palabra; con LRC normal se sigue la frase.

`singlayer recognize` solo abre SongRec si ya está instalado. Todavía no enlaza sus
resultados automáticamente con el karaoke. No se instala nada en el navegador ni
se activa la captura de sonido sin intervención del usuario.

Créditos y licencias: [THIRD_PARTY.md](THIRD_PARTY.md).
# Panel de control (nuevo)

Ejecuta `.venv/bin/singlayer app` para abrir una ventana nativa con conexión,
canción, reloj y resultado de la búsqueda de letras. Pulsa «Conectar y abrir
letras». El overlay se inicia cuando el conector recibe una canción. Cerrar
esta ventana detiene solo los procesos que ella inició.

Si tenías `singlayer start` abierto, ciérralo antes con Ctrl+C: esa versión no
expone el nuevo estado. La ventana no puede leer los resultados de un overlay
iniciado por separado. Un resultado de letras no demuestra sincronía de un remix.
SongRec automático y corrección de velocidad siguen pendientes.
