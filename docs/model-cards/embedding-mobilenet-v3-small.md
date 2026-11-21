# Model card: `embedding.person.mobilenet_v3_small`

| Campo | Valor |
|---|---|
| ID | `embedding.person.mobilenet_v3_small` |
| Nombre | `mobilenet_v3_small` |
| Versión | `1.0.0` (`artifact_version: IMAGENET1K_V1`) |
| Tarea | `embedding` |
| Selector | `mobilenet_v3_small` |
| Hash/checksum | `unverified` |
| Registro | `config/models.yml` |
| Fecha de registro | `2026-11-21` |

## Uso previsto

Extraer un embedding normalizado de 576 dimensiones a partir de un recorte BGR `uint8`
de una persona detectada. Es el extractor por defecto del pipeline de Vision Core.

## Fuera de uso

No identifica personas por nombre ni verifica identidad. No se usa para reconocimiento
facial, clasificación de atributos sensibles ni como métrica de aforo certificada. Los
embeddings se comparan solo entre tracks del mismo despliegue.

## Datos de entrenamiento o proveniencia conocida

`torchvision.models.mobilenet_v3_small` con `MobileNet_V3_Small_Weights.DEFAULT`, que
corresponde a `IMAGENET1K_V1` y sus transformaciones. Fuente consultada el
`2026-11-21`: <https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.mobilenet_v3_small.html>.
Los pesos se descargan a la caché de torchvision si no están presentes.

## Métricas del ticket 36

| Métrica | Valor | Origen |
|---|---:|---|
| acc@1 / acc@5 ImageNet-1K publicadas | 67.668 / 87.402 | Documentación oficial torchvision |
| Dimensión del embedding local | 576 | `config/models.yml` y arquitectura del modelo |
| FPS y latencias del pipeline combinado | Ver `reports/synthetic-performance.json` | Medición sintética conjunta con YOLOv8n |
| Precisión de ReID con pares reales | No medida | Sin datos anotados de la sala |

Las métricas de ImageNet no son métricas de ReID; solo describen la proveniencia de los
pesos. La ejecución local no separó el coste ni la precisión del extractor.

## Limitaciones y sesgos conocidos

- Los pesos provienen de ImageNet-1K, no de un dataset de personas de la sala; su
  comportamiento ante uniforms, oclusiones, baja luz o cambios de cámara no está validado.
- El umbral de similitud (`VISION_CORE_REID_THRESHOLD`) no ha sido calibrado con pares
  reales positivos y negativos.
- Cada recorte se transforma con la transformación oficial de los pesos; cambiar el
  perfil de pesos sin actualizar el registro cambia la salida.
- `checksum: null` porque los pesos viven en la caché de torchvision y no hay una copia
  local verificada en el repositorio.

## Dependencias y licencias

| Componente | Versión declarada | Licencia |
|---|---|---|
| `torchvision` | `0.25.0` en `requirements-cpu.txt` | BSD-3-Clause para el código |
| Pesos `IMAGENET1K_V1` | Fijados por el enum de torchvision | No declarada en metadatos (`UNKNOWN`) |
| `torch` / `opencv-python` / `pillow` | Ver `requirements*.txt` | Según paquetes |

Los metadatos de torchvision advierten que los pesos pueden tener términos propios
derivados del dataset. La revisión legal queda pendiente del ticket 42.

## Configuración esperada

`VISION_CORE_EMBEDDING_MODEL_ID=embedding.person.mobilenet_v3_small`,
`VISION_CORE_EMBEDDING_MODEL=mobilenet_v3_small`,
`VISION_CORE_EMBEDDING_WEIGHTS=DEFAULT`. Para verificar checksum, definir
`VISION_CORE_EMBEDDING_WEIGHTS_PATH` con el archivo local.

## Procedimiento de rollback

1. Restaurar la caché o el archivo apuntado por `VISION_CORE_EMBEDDING_WEIGHTS_PATH`.
2. Fijar `VISION_CORE_EMBEDDING_MODEL_ID=embedding.person.mobilenet_v3_small` y volver a
   la entrada anterior del registro si se había adoptado otra versión.
3. Reiniciar y comprobar `embedding.model_id` y `model_version` en `/ready`.

## Verificación

Ejecutar la validación de `docs/validation.md` con `VISION_CORE_EMBEDDING_DEVICE=cpu` y
comparar `/ready` y los logs con la versión anterior.
