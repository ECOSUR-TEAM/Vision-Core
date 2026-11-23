# Model card: `embedding.person.mobilenet_v3_small.fp16`

| Campo | Valor |
|---|---|
| ID | `embedding.person.mobilenet_v3_small.fp16` |
| Nombre | `mobilenet_v3_small-fp16` |
| Versión | `1.0.0` (`artifact_version: IMAGENET1K_V1+FP16`) |
| Tarea | `embedding` |
| Selector | `mobilenet_v3_small-fp16` |
| Hash/checksum | `unverified` (pesos torchvision en caché, sin archivo versionado) |
| Registro | `config/models.yml` |
| Fecha de registro | 2026-11-22 |

## Uso previsto

Extracción de embeddings de 576 dimensiones en GPU con precisión FP16. Útil como
referencia de hardware edge con CUDA; no aplica a CPU.

## Fuera de uso

No se ejecuta en CPU. No se usa en la suite sin CUDA: la fila correspondiente queda
marcada como `unsupported`.

## Datos de entrenamiento o proveniencia conocida

Misma base que `embedding.person.mobilenet_v3_small`: torchvision MobileNet_V3_Small con
`IMAGENET1K_V1`, convertida a mitad de precisión en el adaptador.

## Métricas del ticket 36

| Métrica | Valor | Origen |
|---|---:|---|
| p50/p95, recall relativo, memoria | Sin medir en CPU | `benchmarks/edge-matrix.*` (fila `gpu-fp16`) |

## Limitaciones y sesgos conocidos

- Requiere CUDA; el benchmark manual de esta tarea no instala ni exige CUDA.
- FP16 puede alterar la norma de embeddings; el adaptador normaliza antes de devolverlos.
- Sin datos anotados solo se mide consistencia relativa contra FP32.

## Dependencias y licencias

| Componente | Versión | Licencia |
|---|---|---|
| torchvision | `requirements.txt` | BSD-3-Clause |
| Pesos ImageNet | `IMAGENET1K_V1` | Ver ticket 42 |

## Configuración esperada

`VISION_CORE_EMBEDDING_MODEL=mobilenet_v3_small-fp16`,
`VISION_CORE_EMBEDDING_MODEL_ID=embedding.person.mobilenet_v3_small.fp16`,
`VISION_CORE_EMBEDDING_PRECISION=fp16`, `VISION_CORE_EMBEDDING_DEVICE=cuda`.

## Procedimiento de rollback

1. Fijar `VISION_CORE_EMBEDDING_MODEL=mobilenet_v3_small`, precisión `fp32`, dispositivo `cpu` y el `model_id` baseline.
2. Reiniciar y verificar `/ready`.

## Verificación

`python -m vision_core.scripts.benchmark_edge --config benchmarks/edge-config.json --target gpu-fp16`.
