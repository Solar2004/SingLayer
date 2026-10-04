# Activar el análisis automático de SingLayer

La conexión se confirmó funcionando en la sesión SoundCloud del usuario después de reiniciar el puente antiguo. Para una instalación nueva, carga **una vez** la extensión «SingLayer — enlace automático» en Brave; WebNowPlaying sigue siendo necesario para el reloj y los controles.

1. En Brave, abre el menú **Extensiones → Gestionar extensiones**.
2. Activa **Modo desarrollador** y pulsa **Cargar descomprimida**.
3. Selecciona esta carpeta preparada:

```text
/home/artorias/.local/share/singlayer/source-link
```

4. Recarga la pestaña de SoundCloud o YouTube. A partir de ahí, reproduce música normalmente; no tienes que copiar enlaces ni pulsar «Analizar» por canción.

La extensión lee únicamente el enlace, título y duración del reproductor actual de SoundCloud o YouTube y los entrega a SingLayer por loopback local. No lee el historial, no envía datos a un servidor externo y no reemplaza WebNowPlaying. Es software propio de este repositorio, bajo MIT. No requiere permisos de historial ni de todas las páginas web.

En SoundCloud utiliza el enlace del minirreproductor, por lo que funciona aunque estés en una lista o en el historial. En YouTube utiliza el identificador del vídeo abierto y su duración. YouTube Music tiene extracción preparada, pero no se ha verificado en una sesión real. Los demás proveedores conservan el análisis desde enlace manual.

SingLayer espera un enlace estable y que coincidan título y duración con la pista activa. Inicia el análisis completo una vez por pista/motor, conserva sus tiempos al hacer seek y cancela el trabajo al cambiar de canción o de versión. Si hay enlaces ambiguos, una descarga falla o la canción está restringida, no sustituye la versión por otra: conserva la recuperación acústica en vivo cuando está disponible. «Solo catálogo» respeta la elección manual y no inicia análisis completos automáticos. La primera escucha puede adelantarse al análisis: aún tarda minutos; los tiempos y las transcripciones son estimados.

## Verificación

- 202 pruebas Python pasan; 4 comprobaciones de extracción JavaScript pasan; Ruff, sintaxis JS/shell y diff check pasan.
- El disparo automático del panel se ejercitó con el resultado acústico real de SoundCloud guardado: 42 líneas aceptadas por el panel y el protocolo del overlay.
- Conexión real de la extensión confirmada en Brave/SoundCloud: URL, título y duración coinciden con la pista activa. YouTube mantiene pruebas de extracción/componentes; no se ha confirmado aquí la extensión instalada en una sesión YouTube.
- El enlace confirmado tiene prioridad sobre una búsqueda de catálogo pendiente, para evitar esperas largas antes de descargar. La barra distingue captura con segundos restantes e inferencia sin porcentaje inventado.
