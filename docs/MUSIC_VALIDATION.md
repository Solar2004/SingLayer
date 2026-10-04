# Pruebas musicales reales — 2026-10-04

Se descargaron fragmentos públicos sin playlist mediante yt-dlp y se decodificaron
con FFmpeg a mono PCM16/16kHz. Cada ventana de 12 segundos se envió al reconocedor
ShazamIO aislado y a la API CrisperWhisper2.0 small CPU int8 persistente. LRCLIB
real proporcionó los catálogos. Sin audio, letras completas ni pesos en Git.

| Grabación | Fragmentos del upload | Shazam | Palabras Crisper por ventana | Idiomas detectados | Alineación de catálogo |
|---|---|---|---|---|---|
| After Dark slowed/reverb/muffled | 30–42, 42–54, 70–82, 82–94 s | 4/4 Mr.Kitty | 0, 0, 0, 0 | en | ninguna |
| Night Changes sped up | 40–52, 52–64 s | 2/2 One Direction | 23, 16 | en | ninguna |
| Night Dancer sped up | 30–42, 42–54, 70–82, 82–94 s | 4/4 IMASE | 1, 0, 1, 34 | ja, ja, en, ja | ninguna |

Fuentes:
- https://soundcloud.com/user-131554924/mr-kitty-after-dark-slowed
- https://soundcloud.com/kaja_roblox-cz/night-changes-sped-up
- https://soundcloud.com/altvile/night-dancer-imase-sped-up

El canto inglés produjo palabras válidas con tiempos medidos, pero pertenecía a
un estribillo repetido: el matcher rechazó la ocurrencia ambigua correctamente.
Las otras transcripciones vacías o incompletas no demuestran ausencia de voz.
La detección japonesa también falló en una ventana. No se midió WER contra una
transcripción humana ni error temporal contra anotaciones; no hay una cifra de
precisión universal. Inferencia caliente aproximada 5–9 s por ventana12s; primera
muestra56s con contención de otro proceso CPU, no una medición aislada de rendimiento.

La identidad funciona en estas muestras. No significa que sus relojes originales
sirvan para el upload editado, ni que Crisper small garantice karaoke automático.
La calibración manual de dos referencias sigue siendo la ruta disponible para
cambios constantes de velocidad; cortes/reordenaciones necesitan evidencia local.

## Correcciones verificadas

- Captura PipeWire nativa de Brave por serial del nodo. Grafo observado enlazó
  exclusivamente Brave al grabador; ningún micrófono ni monitor global.
- PulseAudio sigue disponible; pw-record no reconecta ni cambia a otro nodo.
- Ajustes de navegador ahora afectan probe, Shazam, medidor y transcripción.
  Auto rechaza múltiples fuentes ambiguas; selección explícita distingue browsers.
- Se rechazan streams silenciados. Al acabar las pruebas Brave estaba muted y
  Vivaldi audible; no se desactivó el mute del usuario ni se capturó Vivaldi como Brave.
- Títulos con barras, bass boosted, 8D, velocidades numéricas, slowed to perfection
  y TikTok generan búsqueda normalizada sin convertir el efecto en artista.
- 118 pruebas completas, Ruff y git diff check pasan.

## Pendiente para karaoke automático robusto

Mejorar/validar canto multilingüe con un modelo adecuado y anotaciones temporales,
y resolver repeticiones con varias referencias acústicas independientes. RX590
Vulkan visible, pero la fuente original C++ CrisperWhisper retorna404: GPU no lista.
