# Evaluación de la sala — estado al 2026-11-03

La validación en condiciones reales está pendiente: no hay un stream accesible ni
una grabación anotada de la sala. No se han medido precisión, recall, cambios de
identidad ni latencia de captura reales. No hay evidencia para certificar una
capacidad máxima de personas.

## Medición disponible

Se ejecutaron YOLOv8n, tracking, MobileNetV3-Small en CPU, ReID y zonas sobre 35
frames de un video sintético que desplaza la imagen bus.jpg. Resultado guardado
en `reports/synthetic-performance.json`:

| Métrica | Resultado |
|---|---:|
| FPS de procesamiento completo | 15.89 |
| FPS del pipeline | 5.55 |
| Tiempo por frame p50 / p95 / p99 | 59.49 / 69.70 / 131.89 ms |
| Lectura media | 5.14 ms |
| Eventos | 1 entrada, 1 salida |
| Latencia captura → evento | No medida |

Los tiempos incluyen primera inferencia, extracción por persona, tracking, ReID,
analítica y parte del registro. El FPS de pipeline incluye apertura, lectura y
registro, pero excluye construcción explícita de modelos. El tiempo total incluye
la inicialización. No se hizo calentamiento; es una ejecución corta, no una
medida estable de capacidad. Las pruebas de suite se ejecutaban simultáneamente,
por lo que puede haber contención de CPU. Repetir sin otras cargas antes de ajustar.

## Protocolo para la sala

Grabar y anotar por separado: sala vacía, una persona, varias personas con aforo
representativo, cruces, oclusiones parciales/totales, entradas/salidas y cambios de
iluminación. Registrar duración, resolución, FPS fuente, modelo, hardware, número
de personas y condiciones de cada toma. Mantener cámara y zonas fijas. Separar
videos usados para ajustar parámetros de videos de evaluación final. Repetir las
mediciones con iguales condiciones y sin cargas ajenas.

```bash
VISION_CORE_EMBEDDING_DEVICE=cpu python -m scripts.validate_pipeline \
  --video sala.avi --zones config/zones.json --frames 3000 --output sala.jsonl
python -m scripts.evaluate_room sala.jsonl anotaciones.json
```

Las anotaciones son una lista JSON. Los frames empiezan en 1 y deben corresponder
exactamente a la grabación reproducida; `id` representa a una persona real y se
mantiene tras oclusiones. `bbox` está en píxeles xyxy:

```json
[
  {"frame": 1, "persons": [{"id": "persona-A", "bbox": [20, 30, 80, 200]}]},
  {"frame": 2, "persons": []}
]
```

Anotar exhaustivamente todas las personas visibles en cada frame evaluado, sin
usar las predicciones como verdad. No incluir personas completamente ocultas;
marcar su misma identidad al reaparecer. Los frames omitidos no se puntúan. Una
lista vacía significa que no hay personas visibles, no que falte la anotación.

El evaluador asocia cajas uno a uno por IoU descendente (mínimo 0.5 configurable).
Informa TP, FP, omisiones, precisión, recall y cambios de track/persona respecto
a la última observación asociada, incluso tras huecos. Es una métrica diagnóstica
con matching greedy, no IDF1/HOTA ni una implementación oficial de MOT. Los cambios
locales pueden ser esperados después de caducar el track; revisar manualmente los
cambios persistentes y los casos ambiguos de solapamiento. Segmentar las anotaciones
por escena permite comparar oclusiones y aforos. No se calcula tasa de identidades
incorrectas sin referencias manuales.

Para medir latencia cámara→evento hacen falta timestamps de captura y relojes
sincronizados, o una prueba visual con reloj visible. Los tiempos de procesamiento
no incluyen buffers anteriores a `read()`. Registrar además el retraso deliberado
de confirmación de zona (3 observaciones), que depende del FPS efectivo.

## Ajustes propuestos, pendientes de evidencia real

- Si crecen omisiones: revisar iluminación, tamaño de persona y resolución antes
  de reducir confianza; comparar precisión y recall al variar el umbral.
- Si aparecen falsos positivos: revisar anotaciones/zonas y evaluar subir el
  umbral; comprobar el aumento de omisiones asociado.
- Si predominan cambios locales en cruces: revisar IoU y predicción de movimiento;
  comparar un tracker con apariencia solo si las escenas muestran esa necesidad.
- Si cambia `person_id` tras oclusiones: revisar recortes, embeddings y umbral ReID
  con pares reales positivos/negativos; ajustar TTL según duración observada.
- Si FPS cae con aforo: medir coste de embeddings por persona; comparar GPU si
  está disponible y una menor frecuencia de extracción, conservando precisión.
- Si hay eventos repetidos cerca del borde: corregir zonas y comparar confirmación
  de 3 frente a más observaciones, midiendo también el retraso adicional.

No se cambiaron umbrales con base en el video sintético. La aceptación real sigue
pendiente del material de la sala y de los objetivos de FPS/latencia/precisión.
