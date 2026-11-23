# Model card: `detection.person.yolov8n.int8`

| Campo | Valor |
|---|---|
| ID | `detection.person.yolov8n.int8` |
| Nombre | `yolov8n-int8` |
| Versión | `1.0.0` (`artifact_version: int8-onnx`) |
| Tarea | `detection` |
| Selector | `yolov8n-int8.onnx` |
| Hash/checksum | `unverified` (artefacto externo; calcular SHA-256 al generarlo) |
| Registro | `config/models.yml` |
| Fecha de registro | 2026-11-22 |

## Uso previsto

Detección de personas en CPU edge mediante un artefacto ONNX INT8 externo. Comparte
confianza 0.5 y clase COCO 0 con el baseline FP32.

## Fuera de uso

No se descarga ni versiona el artefacto en este repositorio. No se usa para medir
precisión absoluta sin ground truth anotado.

## Datos de entrenamiento o proveniencia conocida

Derivado de Ultralytics YOLOv8n preentrenado en COCO. Generación sugerida:
`yolo export model=yolov8n.pt format=onnx int8=True` (requiere dependencias ONNX en el
entorno de exportación, no en el runtime de benchmark).

## Métricas del ticket 36

| Métrica | Valor | Origen |
|---|---:|---|
| p50/p95, FPS, memoria, precisión | Pendiente | `benchmarks/edge-matrix.*` (fila `cpu-int8`) |

## Limitaciones y sesgos conocidos

- El backend ONNX debe estar disponible en el target; sin él la fila queda `not_measured`.
- Cuantización sin reentrenamiento: puede reducir recall en objetos pequeños o con iluminación baja.
- El hash real debe registrarse en `config/models.yml` antes de recomendación en producción.

## Dependencias y licencias

| Componente | Versión | Licencia |
|---|---|---|
| Ultralytics | `requirements.txt` | AGPL-3.0 |
| ONNX Runtime (opcional) | externo | MIT |

## Configuración esperada

`VISION_CORE_DETECTION_MODEL_ID=detection.person.yolov8n.int8`,
`VISION_CORE_MODEL_PATH=yolov8n-int8.onnx`, `VISION_CORE_DETECTION_PRECISION=int8`,
`VISION_CORE_DETECTION_DEVICE=cpu`.

## Procedimiento de rollback

1. Restaurar `yolov8n.pt`, precisión `fp32` y el `model_id` del baseline.
2. Reiniciar y comprobar `/ready`.

## Verificación

`python -m vision_core.scripts.benchmark_edge --config benchmarks/edge-config.json --target cpu-int8 --model-dir <dir>`.
