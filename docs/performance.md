# Presupuestos de rendimiento y benchmark nocturno

Este documento define los presupuestos, el método de medición y la política de
regresiones. El benchmark usa el pipeline secuencial real (`RunPipeline`) con un
video sintético reproducible; no es una medición de precisión ni una prueba de
carga multi-cámara.

## Escenarios y presupuestos

Las cifras vivas están en [`benchmarks/budgets.json`](../benchmarks/budgets.json).
El workflow nocturno las aplica con `--fail-on-budget`; el smoke de PR usa el
escenario `pr-smoke` con umbrales deliberadamente amplios.

| Escenario | FPS mínimo | Frame p95 | Inferencia p95 | Memoria pico | Crecimiento/h | Arranque | Reconexión | Tolerancia |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `synthetic-cpu-320x240` | 30 | 60 ms | 40 ms | 512 MB | 1024 MB | 8 s | 3 s | 10% |
| `synthetic-cpu-640x480` | 15 | 120 ms | 100 ms | 768 MB | 1536 MB | 10 s | 3 s | 15% |
| `synthetic-gpu-640x480` | 25 | 80 ms | 70 ms | 1536 MB | 1024 MB | 15 s | 3 s | 15% |
| `pr-smoke` | 5 | 500 ms | 500 ms | 2048 MB | 2048 MB | 30 s | 30 s | 50% |

El escenario GPU es una referencia para runners con CUDA; no forma parte de la
matriz de GPUs ni corre en el runner estándar. Para usarlo hay que fijar el modelo
y registrar `VISION_CORE_*`, versión de PyTorch y driver en el reporte.

## Método

1. `vision_core.scripts.create_benchmark_video` genera un MJPEG determinista
   (semilla `20261120`, generador `1.0.0`), `zones.json` y `scene.json`. El video
   contiene marcas blancas/rojas que recorren exterior → interior → exterior →
   fuera.
2. `vision_core.scripts.benchmark_nightly` construye `FileVideoSource`,
   `SyntheticDetector`, `InMemoryReID`, `PolygonDoorAnalytics` y la serialización
   real del evento con `event_to_json`. El pipeline procesa los 450 frames sin
   saltarse etapas.
3. `FrameProfiler` entrega p50/p95 por etapa: `decode`, `detection`, `embedding`,
   `reid_tracking`, `analytics`, `serialization` y `frame_total`.
 4. La memoria se mide con `tracemalloc` en todos los sistemas y con `VmRSS`/`VmHWM`
    de `/proc/self/status` cuando el runner es Linux. El reporte indica la fuente
    usada, pero la tendencia usa siempre el delta de `tracemalloc` para que el
    resultado sea comparable entre plataformas. Con ejecuciones cortas se normaliza
    con una ventana mínima de 30 s antes de extrapolar a una hora, y la regresión de
    memoria usa un suelo de 10 MB/h.
5. El arranque se mide hasta el primer frame processado y la reconexión con un
   `RtspVideoSource` alimentado por una captura simulada: exercisea el código de
   reintento sin abrir sockets.

La configuración queda fijada en el artefacto: versión del generador, hash del
video, resolución, fps, dispositivo declarado, detector, Python, NumPy, OpenCV y
Ultralytics. No se descarga nada y no se necesita RTSP, GPU ni internet.

## Métricas

- `fps`: frames procesados / tiempo transcurrido del profiler.
- `frame_p50_ms`, `frame_p95_ms`: latencia del frame completo.
- `inference_p50_ms`, `inference_p95_ms`: etapa `detection`, comparable con
  `vision_core_inference_latency_ms`.
- `serialization_p95_ms`: coste de `event_to_json` por evento.
- `memory_peak_mb`, `memory_growth_mb_per_hour`: pico y tendencia.
- `startup_ms`, `reconnect_ms`: arranque a primer frame y recuperación simulada.
- `hotspots`: etapas ordenadas por p95.

Los contadores de `ObservabilityMetrics` se guardan como telemetría de apoyo; el
gate usa las mediciones del profiler para no depender del singleton global.

## Regresiones

`compare_baseline` compara el resultado contra
`benchmarks/baseline-<escenario>.json`. Para FPS, un descenso mayor que la
tolerancia es regresión; para latencia, memoria y tiempos de arranque/reconexión,
lo es un ascenso mayor que la tolerancia. El workflow nocturno falla con
`--fail-on-regression` cuando hay baseline; los baselines shippeados son una
referencia de Windows local y conviene regenerarlos en el runner de CI antes de
considerarlos oficiales.

El smoke de PR no compara contra baseline: solo verifica que no haya una ruptura
grande. Las fluctuaciones normales no bloquean el PR. El nightly sí aplica los
presupuestos estrictos y publica un resumen en el job.

## Comandos

```bash
# Generar video, ejecutar el benchmark y aplicar presupuestos (320x240)
make benchmark

# Equivalente explícito con comparación contra baseline
python -m vision_core.scripts.create_benchmark_video benchmark-data/synthetic-cpu-320x240 \
  --frames 450 --fps 15 --width 320 --height 240 --allow-existing
python -m vision_core.scripts.benchmark_nightly \
  --scenario synthetic-cpu-320x240 \
  --video benchmark-data/synthetic-cpu-320x240/benchmark.avi \
  --zones benchmark-data/synthetic-cpu-320x240/zones.json \
  --scene benchmark-data/synthetic-cpu-320x240/scene.json \
  --budgets benchmarks/budgets.json \
  --baseline benchmarks/baseline-synthetic-cpu-320x240.json \
  --output benchmark-synthetic-cpu-320x240.json \
  --fail-on-budget --fail-on-regression

# Regenerar un baseline después de un cambio intencional de hardware/modelo
python -m vision_core.scripts.benchmark_nightly ... \
  --write-baseline benchmarks/baseline-synthetic-cpu-320x240.json

# Humo de PR y suite pesada
make smoke
make e2e
```

Cada ejecución escribe JSON, CSV y Markdown. El nightly sube esos archivos y
`benchmark-nightly.log` como artefactos; el job de PR sube `performance-smoke.json`.

## Hotspots conocidos

El informe generado a partir del baseline está en
[`reports/performance-hotspots.md`](../reports/performance-hotspots.md). El orden
observado con el detector sintético suele ser captura/decode, detección,
serialización, ReID, zonas y embedding. Con un modelo real, la detección suele
dominar; el extractor ReID y la serialización crecen con el número de personas.
No se optimizan modelos en este ticket: solo se hace visible el coste por etapa.

## Verificación

1. `pytest tests/performance -m performance`.
2. `pytest -m smoke` comprueba el umbral amplio sobre el video de 35 frames.
3. `tests/performance/test_benchmark_analysis.py` introduce una regresión
   artificial de FPS y p95 y confirma que se detecta, además de comprobar que una
   fluctuación del 1%/2% no se marca como regresión.
4. El workflow `benchmark.yml` publica el resumen y los artefactos; `e2e.yml`
   cubre el monitor y `ci.yml` la cobertura y el smoke.
