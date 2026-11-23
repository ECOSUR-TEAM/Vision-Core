# Model card: `detection.person.yolov8n.fp16`

| Campo | Valor |
|---|---|
| ID | `detection.person.yolov8n.fp16` |
| Nombre | `yolov8n-fp16` |
| Versión | `1.0.0` (`artifact_version: fp16-cuda`) |
| Tarea | `detection` |
| Selector | `yolov8n-fp16.pt` |
| Hash/checksum | `unverified` (artefacto externo; calcular SHA-256 al generarlo) |
| Registro | `config/models.yml` |
| Fecha de registro | 2026-11-22 |

## Uso previsto

Detección de personas en frames BGR uint8 con CUDA. Es una variante de precisión del
mismo modelo base que `detection.person.yolov8n`; comparte confianza 0.5 y clase COCO 0.

## Fuera de uso

No se ejecuta en CPU. No sustituye la validación con datos anotados ni mide precisión
absoluta en el dataset objetivo.

## Datos de entrenamiento o proveniencia conocida

Derivado de Ultralytics YOLOv8n preentrenado en COCO. El artefacto FP16 se genera fuera
del repositorio cargando `yolov8n.pt`, aplicando `model.half()` y guardando
`yolov8n-fp16.pt` en hardware CUDA; el selector del registro exige extensión `.pt`.

## Métricas del ticket 36

| Métrica | Valor | Origen |
|---|---:|---|
| p50/p95, FPS, memoria, precisión | Pendiente | `benchmarks/edge-matrix.*` (fila `gpu-fp16`) |

Sin hardware CUDA no hay medición: la fila se publica como `unsupported`.

## Limitaciones y sesgos conocidos

- Requiere CUDA y una licencia Enterprise/AGPL compatible para el artefacto exportado.
- FP16 puede degradar confianza en objetos pequeños; verificar contra el umbral de calidad.

## Dependencias y licencias

| Componente | Versión | Licencia |
|---|---|---|
| Ultralytics | `requirements.txt` | AGPL-3.0 |
| Pesos YOLOv8n | `unpinned` | AGPL-3.0 |

## Configuración esperada

`VISION_CORE_DETECTION_MODEL_ID=detection.person.yolov8n.fp16`,
`VISION_CORE_MODEL_PATH=yolov8n-fp16.pt`, `VISION_CORE_DETECTION_PRECISION=fp16`,
`VISION_CORE_DETECTION_DEVICE=cuda`, confianza 0.5, clases `0`.

## Procedimiento de rollback

1. Restaurar `yolov8n.pt` y `VISION_CORE_DETECTION_PRECISION=fp32`.
2. Fijar `VISION_CORE_DETECTION_MODEL_ID=detection.person.yolov8n`.
3. Reiniciar y verificar `model_id`, `precision` y `model_hash` en logs y `/ready`.

## Verificación

`python -m vision_core.scripts.benchmark_edge --config benchmarks/edge-config.json --profile gpu-fp16 --allow-cuda --model-dir <dir>`.
La recall de identidad exige `validation_set.identity_gallery`.
