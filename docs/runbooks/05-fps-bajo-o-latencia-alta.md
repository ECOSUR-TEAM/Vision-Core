# Runbook 05: FPS bajo o latencia alta

**Síntoma:** el monitor se ve lento, `vision_core_fps` baja, aumentan frames
descartados o el p95 de procesamiento crece.

## Verificación rápida

```bash
curl http://127.0.0.1:8080/metrics
docker stats --no-stream
```

Compara estos campos de `/metrics`:

| Señal | Qué indica |
|---|---|
| `vision_core_frames_processed_total` | Frames que entraron al pipeline |
| `vision_core_frames_discarded_total` | Frames descartados por conservar solo el más reciente |
| `vision_core_fps` | FPS suavizado del monitor |
| `vision_core_inference_latency_ms` | Coste de detección |
| `vision_core_reid_latency_ms` | Coste de embedding y ReID |
| `vision_core_frame_processing_duration_ms` | Coste total por frame |

Si hace falta desglose, activa el profiling opt-in y compara el informe con la
línea base:

```bash
VISION_CORE_PROFILING_ENABLED=1 VISION_CORE_PROFILING_OUTPUT=profiling_results.json \
  python main.py
```

Etapas medidas: `decode`, `detection`, `embedding`, `reid_tracking`,
`analytics` y `frame_total`.

## Acción

1. **Captura:** `VISION_CORE_DECODER_THREADS=1` reduce el búfer de salida de
   OpenCV. `0` usa selección automática y puede añadir retraso; no lo cambies
   sin medir.
2. **Carga:** revisa CPU/GPU con `docker stats`. La configuración probada es
   CPU; CUDA explícita requiere driver y torch/torchvision compatibles.
3. **Resolución y detección:** reducir resolución de entrada o ajustar
   `VISION_CORE_DETECTION_CONFIDENCE` puede bajar el coste. Cualquier cambio de
   resolución o encuadre obliga a recalibrar zonas; ver
   [06. No se generan eventos](06-no-se-generan-eventos.md).
4. **Render:** con `VISION_CORE_RENDER_ENABLED=0` (o `--no-render`) se omite
   JPEG. Es útil para medir el pipeline sin visor; el monitor dejará de mostrar
   frames.
5. **Ojo con los flags preparatorios:** `VISION_CORE_EMBEDDING_BATCH_SIZE` y
   `VISION_CORE_EMBEDDING_STRIDE` se leen hoy pero **no** cambian la inferencia.
   No los presentes como solución.
6. **Latencia real:** el tiempo de `read()` o de inferencia no mide la latencia
   cámara→evento. Para medirla hace falta una prueba con reloj visible o
   timestamps de captura. Compara también el restream original de Frigate para
   separar red, decodificación y analítica.
7. **Presupuestos:** contrasta con
   [retraso del video](../operations.md#retraso-del-video) y con los informes de
   evaluación antes de declarar regresión; las cifras de la sala todavía no
   están certificadas.

## Señal de éxito

- `vision_core_fps` vuelve al rango esperado para el entorno y
  `vision_core_frame_processing_duration_ms` no crece de forma sostenida.
- `vision_core_frames_discarded_total` deja de aumentar ritmo tras el ajuste.
- La latencia medida con reloj visible está dentro del objetivo acordado.

## Escalado

Si el cuello está en inferencia y el equipo no tiene GPU, registra p50/p95,
resolución y versión de modelos, y escala al responsable de rendimiento. No
subas el timeout de lectura como sustituto de una optimización. Más detalle en
[monitor.md](../monitor.md#implementación-y-acceso) y
[operations.md](../operations.md#retraso-del-video).
