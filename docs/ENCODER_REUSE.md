# Menos cálculo repetido en Whisper Vulkan

El instalador aplica `patches/whisper-reuse-language-encoder.patch` a whisper.cpp fijado en `60c0be6ac8fa71b1a2ae2dd938a31a34a508e774`. La detección automática del idioma ya codifica el comienzo del audio. La transcripción reutiliza esa codificación cuando el comienzo y el contexto coinciden y no hay callback del codificador. Otros casos siguen el camino original. Cada fragmento sigue detectando su propio idioma; se conservan large-v3-turbo Q5_0, Vulkan y DTW.

## Comparación real en RX 590

Mismo audio de 24 segundos, servidor original y servidor modificado, ejecución secuencial. Se compararon los segmentos JSON completos y el documento con tiempos que consume SingLayer: coincidencia exacta en los cinco casos.

| Fragmento | Idioma detectado | Original | Optimizado |
|---|---|---:|---:|
| Night Changes sped up | Inglés | 12,010 s | 8,231 s |
| Night Dancer | Japonés | 11,807 s | 8,099 s |
| After Dark | Inglés | 12,124 s | 8,549 s |
| Honeypie slowed | Inglés | 11,764 s | 8,054 s |
| Moi… Lolita | Francés | 12,370 s | 8,788 s |

Reducción de aproximadamente 29–32% del tiempo de inferencia observado. Son pruebas individuales, no un benchmark estadístico ni una comparación con letras humanas. Con idioma explícito y comienzo desplazado también se conservó la salida, sin aceleración significativa. Un experimento adicional con contexto reducido produjo tiempos rechazados por el validador; no se activa ese ajuste. El contexto de producción permanece sin reducción.

## Instalación y validación

```sh
bash scripts/setup-whisper-vulkan.sh
```

El script comprueba revisión y checkout limpio, aplica el parche, compila, verifica el modelo por SHA256 y ejecuta una inferencia real con Vulkan. Al salir restaura la fuente de la dependencia. `ready.json` registra el perfil `reuse-language-encoder-v1` y hashes de biblioteca/parche. SingLayer rechaza una biblioteca o un parche alterados para evitar presentar otra compilación como validada. `/health` expone el perfil activo. Las instalaciones anteriores siguen siendo compatibles.

213 pruebas Python pasan, además de Ruff, validación shell y diff check. La prueba binaria con canciones comprueba preservación de salida; los tests Python cubren integridad del runtime y compatibilidad anterior.

## Pista completa sin caché

Night Changes sped up (SoundCloud): 102,076 s frente a150,016 s en la ejecución previa. Primera entrega16,750 s frente a19,750 s; repetición de caché0,2029 s. Cobertura177,3405625 s/11 ventanas. Las ejecuciones completas produjeron43 y42 líneas y documentos diferentes: la preservación exacta queda probada para los fragmentos pareados, no para las ejecuciones completas con planificación progresiva.
