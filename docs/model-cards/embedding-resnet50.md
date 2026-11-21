# Model card: `embedding.person.resnet50`

| Campo | Valor |
|---|---|
| ID | `embedding.person.resnet50` |
| Nombre | `resnet50` |
| Versión | `1.0.0` (`artifact_version: IMAGENET1K_V2`) |
| Tarea | `embedding` |
| Selector | `resnet50` |
| Hash/checksum | `unverified` |
| Registro | `config/models.yml` |
| Fecha de registro | `2026-11-21` |

## Uso previsto

Variante alternativa de extracción de embeddings: produce un vector normalizado de 2048
dimensiones por recorte BGR `uint8` de persona. Se activa de forma explícita con
`VISION_CORE_EMBEDDING_MODEL=resnet50`.

## Fuera de uso

No se usa por defecto ni se ha validado en la sala. No identifica personas por nombre,
no hace reconocimiento facial y no sustituye la calibración de umbrales de ReID.

## Datos de entrenamiento o proveniencia conocida

`torchvision.models.resnet50` con `ResNet50_Weights.DEFAULT`, que corresponde a
`IMAGENET1K_V2` y sus transformaciones. Fuente consultada el `2026-11-21`:
<https://docs.pytorch.org/vision/main/models/generated/torchvision.models.resnet50.html>.
Los pesos se descargan a la caché de torchvision si no están presentes.

## Métricas del ticket 36

| Métrica | Valor | Origen |
|---|---:|---|
| acc@1 / acc@5 ImageNet-1K publicadas | 80.858 / 95.434 | Documentación oficial torchvision |
| Dimensión del embedding local | 2048 | `config/models.yml` y arquitectura del modelo |
| Latencia y FPS de esta variante | No medidos | La medición local usó MobileNetV3-Small |
| Precisión de ReID con pares reales | No medida | Sin datos anotados de la sala |

Antes de adoptar esta variante hay que repetir el benchmark del ticket 36 con
`VISION_CORE_EMBEDDING_MODEL=resnet50` y comparar contra la variante por defecto.

## Limitaciones y sesgos conocidos

- Coste de inferencia superior a MobileNetV3-Small; el presupuesto de FPS puede no
  cumplirse sin medición previa.
- Entrenado sobre ImageNet-1K, no sobre datos de la sala; no hay evidencia de sesgos o
  robustez en uniforms, oclusiones o iluminación variable.
- El cambio de dimensión del embedding no invalida la memoria ReID en memoria, pero sí
  cualquier índice externo que asuma 576 dimensiones; verificar integraciones antes de
  adoptarlo.
- `checksum: null` por estar los pesos en la caché de torchvision sin copia verificada.

## Dependencias y licencias

| Componente | Versión declarada | Licencia |
|---|---|---|
| `torchvision` | `0.25.0` en `requirements-cpu.txt` | BSD-3-Clause para el código |
| Pesos `IMAGENET1K_V2` | Fijados por el enum de torchvision | No declarada en metadatos (`UNKNOWN`) |
| `torch` / `opencv-python` / `pillow` | Ver `requirements*.txt` | Según paquetes |

La revisión legal de los pesos queda pendiente del ticket 42.

## Configuración esperada

`VISION_CORE_EMBEDDING_MODEL_ID=embedding.person.resnet50`,
`VISION_CORE_EMBEDDING_MODEL=resnet50`, `VISION_CORE_EMBEDDING_WEIGHTS=DEFAULT`.
Para verificar checksum, definir `VISION_CORE_EMBEDDING_WEIGHTS_PATH` con el archivo local.

## Procedimiento de rollback

1. Volver a `VISION_CORE_EMBEDDING_MODEL=mobilenet_v3_small`.
2. Fijar `VISION_CORE_EMBEDDING_MODEL_ID=embedding.person.mobilenet_v3_small` y restaurar
   la caché o el archivo local de esa variante.
3. Reiniciar y comprobar `embedding.model_id` y `model_version` en `/ready`.

## Verificación

Repetir `docs/validation.md` y el benchmark nocturno con la misma resolución y hardware
que la variante base antes de promoverla a `active`.
