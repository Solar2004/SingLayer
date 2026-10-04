# Prueba real de música — 2026-10-04

Se ejecutó el servicio instalado Whisper.cpp large-v3-turbo Q5_0 en RX590 Vulkan,
con autoidioma y DTW. Se reprocesaron siete ventanas de audio musical real de
aproximadamente24s, cuatro canciones. No son siete canciones distintas. Las
muestras existentes proceden de uploads públicos de SoundCloud.

| Muestra | Frases transcritas | Líneas alineadas | Inferencia | Shazam |
|---|---:|---:|---:|---|
| Night Changes sped,56–80s |6|2|13.42s|One Direction correcto|
| Night Changes sped,64–88s |6|2|15.74s|One Direction correcto|
| Night Changes estribillo,40–64s |8|0|15.60s|One Direction correcto|
| Night Dancer sped,70–94s |3|1|15.80s|imase correcto|
| After Dark vocal alterada |6|0|15.69s|Mr.Kitty correcto|
| Honeypie slowed/reverb |2|0|14.71s|edición slowed/bass reconocida|
| Night Changes +10% extra, recorte |6|2|16.05s|no solicitado|

Shazam recibió solo audio, sin título/artista:6/6 identificaciones coherentes.
Reconocer una edición comercial no garantiza que su catálogo tenga la letra
original ni los mismos tiempos. Todos los tiempos ASR permanecieron dentro de
su ventana de audio.

## Reloj y recorte desde la mitad

Dos fragmentos Night Changes produjeron cuatro referencias únicas: velocidad
1.23305588585×, desfase2.84205707491s. Al reproducir las mismas transcripciones
con el reloj de un upload que comienza en el segundo56, el desfase cambió a
71.89318668252s y conservó velocidad y correspondencia temporal.

Se simuló un salto de sección desplazando44s la posición de esas mismas ventanas
medidas: el primer fragmento invalidó el reloj anterior; el segundo reunió cuatro
referencias y reconstruyó el reloj con desfase−51.41240190250s. Esto prueba la
integración sobre ASR musical real y relojes controlados; no es un nuevo remix
con empalmes escuchados ni validación humana de cada límite temporal.

## Resultado y límites

La identificación funciona mejor que la alineación en esta tanda. El estribillo
repetido no reunió dos referencias únicas alrededor: cero repeticiones resueltas
por contexto en estas siete ventanas. Permaneció conservador, mostrando texto
transcrito en vez de adivinar su posición original. La mejora contextual pasa
regresiones, pero sigue sin demostración positiva en esta matriz musical real.

After Dark y Honeypie alteradas produjeron texto sin coincidencias fiables con
el catálogo. Todavía no puede afirmarse que todas las variantes estén listas
sin corrección manual. Estos son los próximos casos concretos que mejorar.

No se midió WER ni error contra anotaciones humanas. Los tiempos13–16s son de
inferencia; hay que añadir adquisición24s. No se guardan audio ni letras completas
en el informe o Git. Resultado reproducible resumido: RESULTADOS_MUSICA.json.

Puerta de código anterior:140 pruebas, Ruff y diff check. Esta petición no
modificó el comportamiento del producto.
