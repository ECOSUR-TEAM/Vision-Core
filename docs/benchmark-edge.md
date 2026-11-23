# Matriz comparativa edge / INT8

Esta guía complementa [`performance.md`](performance.md). Describe cómo ejecutar
`vision_core.scripts.benchmark_edge`, cómo interpretar la matriz versionada y qué
evidencia se exige antes de promover una variante INT8 o FP16.

## Perfiles

| Perfil | Target | Dispositivo | Precisión det/emb |
|---|---|---|---|
| `cpu-fp32` | `cpu-laptop` | CPU | FP32 / FP32 |
| `cpu-int8` | `cpu-laptop` | CPU | INT8 / INT8 |
| `jetson-fp32` | `jetson-nano-int8` | CPU ARM | FP32 / FP32 |
| `jetson-int8` | `jetson-nano-int8` | CPU ARM | INT8 / INT8 |
| `gpu-fp16` | `gpu-fp16` | CUDA | FP16 / FP16 |

`cpu-fp32` es el rollback. No se comparan precisiones absolutas: la métrica de
detección es un proxy sobre el video sintético y la de identidad es relativa a
una galería etiquetada.

## Ejecución

```bash
make benchmark-edge

python -m vision_core.scripts.benchmark_edge \
  --config benchmarks/edge-config.json \
  --profile cpu-fp32 \
  --model-dir <dir-con-pesos>

python -m vision_core.scripts.benchmark_edge \
  --config benchmarks/edge-config.json \
  --profile cpu-int8 \
  --model-dir <dir-con-pesos>
```

`--profile` Selecciona un perfil; `--target` selecciona todos los perfiles de un
target. Para CUDA hay que ejecutar en hardware compatible y añadir `--allow-cuda`.
Sin pesos o sin CUDA los perfiles quedan `not_measured`/`unsupported` y no se
emiten recomendaciones para ese target.

## Artefactos externos

- Detección INT8: ONNX cuantizado `yolov8n-int8.onnx`, fuera del repositorio.
- Detección FP16: `yolov8n-fp16.pt` generado con pesos en half en CUDA.
- Embeddings INT8: PTQ FX x86 sobre `MobileNet_V3_Small_Weights.DEFAULT`, con
  calibración sintética determinista; no requiere archivo adicional.
- Embeddings FP16: seleccionan `mobilenet_v3_small-fp16` y requieren CUDA.

Los hashes reales se registran en `config/models.yml` antes de cualquier
promoción. `benchmarks/edge-matrix.json` guarda el SHA del config, el entorno y
el hash del artefacto de detección cuando hay medición.

## Quality gates

La calidad se evalúa antes que el presupuesto:

- `map50_proxy`: correspondencia por frame con IoU >= 0.5 entre predicciones y
  marcadores del scene. Nunca se emparejan cajas de frames distintos.
- `recall_at_1_vs_gallery`: vecino más cercano contra una galería etiquetada.
  La configuración `validation_set.identity_gallery` apunta a un `.npz` con
  `embeddings` (N x D) y `labels` (N). Si no hay galería, el gate queda
  `sin_medicion` y el perfil no puede recomendarse.
- `max_relative_drop_pct`: caída máxima del 5% frente al baseline con medición
  equivalente. No se usa una comparación consigo mismo.

Cuando un perfil falla calidad, `budget.passed` es `null`: FPS no puede compensar
pérdida de precisión.

## Métricas de rendimiento

- `fps_end_to_end`: frames / tiempo de detección + embedding por frame.
- `frame`: p50/p95 de la latencia total por frame; es la serie que consume el
  presupuesto `frame_p95_ms`.
- `detection` y `embedding`: latencias por etapa.
- `memory_peak_tracemalloc_mb`: pico de asignaciones Python; no incluye memoria
  nativa de PyTorch/ONNX, así que debe complementarse con RSS del target.
- `energy_j`: lectura RAPL cuando el sistema expone sensores de paquete.

## Promoción y rollback

Promover una variante exige: medición real en el target, quality gates en verde,
presupuesto en verde y hash registrado. La recomendación del artefacto se limita
al target medido; sin medición, `profile` es `null`.

Para rollback:

1. Restaurar los IDs/pesos FP32 del baseline.
2. Fijar `VISION_CORE_DETECTION_PRECISION=fp32` y
   `VISION_CORE_EMBEDDING_PRECISION=fp32`.
3. Reiniciar y verificar `model_id`, `precision` y `model_hash` en logs y `/ready`.

## Limitaciones

El conjunto sintético sirve para comparar latencias y regresiones relativas, no
para estimar precisión en cámaras reales. La calibración INT8 y los marcadores no
sustituyen datos anotados. La matriz versionada en el repositorio se genera sin
pesos ni hardware externo, por lo que sus filas son `not_measured`/`unsupported`.
