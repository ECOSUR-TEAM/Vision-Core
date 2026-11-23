# Matriz comparativa edge / INT8

- Generado: `2026-11-23T05:53:29.408814+00:00`
- Config: `benchmarks\edge-config.json` (`64fc0f2038c1`)
- Semilla del conjunto de validación: `20261120`
- Calidad se evalúa antes que FPS; umbrales: `{'min_detection_map50': 0.9, 'min_identity_recall_at_1': 0.9, 'max_relative_drop_pct': 5.0, 'baseline_profile': 'cpu-fp32'}`

| Perfil | Target | Precisión det/emb | Estado | Det p50/p95 (ms) | Emb p50/p95 (ms) | FPS | Memoria pico (MB) | map50 proxy | Recall ID | Calidad | Presupuesto | Recomendado |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---|---|---|
| cpu-fp32 | cpu-laptop | fp32/fp32 | not_measured | —/— | —/— | — | — | — | — | NO | — | NO |
| cpu-int8 | cpu-laptop | int8/int8 | not_measured | —/— | —/— | — | — | — | — | NO | — | NO |
| jetson-fp32 | jetson-nano-int8 | fp32/fp32 | not_measured | —/— | —/— | — | — | — | — | NO | — | NO |
| jetson-int8 | jetson-nano-int8 | int8/int8 | not_measured | —/— | —/— | — | — | — | — | NO | — | NO |
| gpu-fp16 | gpu-fp16 | fp16/fp16 | unsupported | —/— | —/— | — | — | — | — | NO | — | NO |

## No medidos

- `cpu-fp32`: Artefacto de detección ausente: models\yolov8n.pt. Los pesos no se versionan en el repositorio.
- `cpu-int8`: Artefacto de detección ausente: models\yolov8n-int8.onnx. Los pesos no se versionan en el repositorio.
- `jetson-fp32`: Artefacto de detección ausente: models\yolov8n.pt. Los pesos no se versionan en el repositorio.
- `jetson-int8`: Artefacto de detección ausente: models\yolov8n-int8.onnx. Los pesos no se versionan en el repositorio.
- `gpu-fp16`: Perfil CUDA omitido: la suite no requiere CUDA; use --allow-cuda en hardware compatible.

## Recomendación

- `cpu-laptop`: `cpu-fp32` — Sin evidencia suficiente: se mantiene FP32 como rollback hasta medir.
- `jetson-nano-int8`: `cpu-fp32` — Sin evidencia suficiente: se mantiene FP32 como rollback hasta medir.
- `gpu-fp16`: `cpu-fp32` — Sin evidencia suficiente: se mantiene FP32 como rollback hasta medir.

Las cifras son del conjunto sintético y de la máquina declarada en `environment`.
Consulta `docs/benchmark-edge.md` antes de promover una variante a producción.
