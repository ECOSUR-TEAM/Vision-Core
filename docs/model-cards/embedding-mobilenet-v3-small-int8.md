# Model card: `embedding.person.mobilenet_v3_small.int8`

| Campo | Valor |
|---|---|
| ID | `embedding.person.mobilenet_v3_small.int8` |
| Nombre | `mobilenet_v3_small-int8` |
| Versión | `1.0.0` (`artifact_version: IMAGENET1K_V1+PTQ-X86`) |
| Tarea | `embedding` |
| Selector | `mobilenet_v3_small-int8` |
| Hash/checksum | `unverified` (pesos torchvision en caché, sin archivo versionado) |
| Registro | `config/models.yml` |
| Fecha de registro | 2026-11-22 |

## Uso previsto

Extracción de embeddings de 576 dimensiones en CPU con cuantización post-entrenamiento
INT8 (backend x86). No requiere reentrenamiento ni pesos nuevos: reutiliza
`MobileNet_V3_Small_Weights.DEFAULT`.

## Fuera de uso

No se ejecuta en CUDA (el backend x86 es CPU-only). No sustituye evaluación de recall
con identidades reales anotadas.

## Datos de entrenamiento o proveniencia conocida

Misma base que el modelo FP32: torchvision MobileNet_V3_Small con IMAGENET1K_V1. La calibración usa recortes
sintéticos deterministas (semilla `20261120`, 8 muestras) generados en el adaptador.

## Métricas del ticket 36

| Métrica | Valor | Origen |
|---|---:|---|
| p50/p95, recall relativo, memoria | Pendiente | `benchmarks/edge-matrix.*` (fila `cpu-int8`) |

## Limitaciones y sesgos conocidos

- La calibración sintética es un proxy de la distribución real: validar con cámara antes de producción.
- FX PTQ depende de la versión de PyTorch; si la API no existe, el adapter falla en arranque.
- Dimensión de salida idéntica al baseline (576), por lo que no cambia el contrato de ReID.

## Dependencias y licencias

| Componente | Versión | Licencia |
|---|---|---|
| torchvision | `requirements.txt` | BSD-3-Clause |
| Pesos ImageNet | `IMAGENET1K_V1` | Ver ticket 42 |

## Configuración esperada

`VISION_CORE_EMBEDDING_MODEL=mobilenet_v3_small-int8`,
`VISION_CORE_EMBEDDING_MODEL_ID=embedding.person.mobilenet_v3_small.int8`,
`VISION_CORE_EMBEDDING_PRECISION=int8`, `VISION_CORE_EMBEDDING_DEVICE=cpu`.

## Procedimiento de rollback

1. Fijar `VISION_CORE_EMBEDDING_MODEL=mobilenet_v3_small`, precisión `fp32` y el `model_id` baseline.
2. Reiniciar y verificar identidad en logs y `/ready`.

## Verificación

`python -m vision_core.scripts.benchmark_edge --config benchmarks/edge-config.json --profile cpu-fp32 --model-dir <dir>` y
`python -m vision_core.scripts.benchmark_edge --config benchmarks/edge-config.json --profile cpu-int8 --model-dir <dir>`.
La galería etiquetada se configura en `validation_set.identity_gallery`.
