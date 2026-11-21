# Model card: `detection.person.yolov8n`

| Campo | Valor |
|---|---|
| ID | `detection.person.yolov8n` |
| Nombre | `yolov8n` |
| Versión | `1.0.0` (`artifact_version: unpinned`) |
| Tarea | `detection` |
| Selector | `yolov8n.pt` |
| Hash/checksum | `unverified` |
| Registro | `config/models.yml` |
| Fecha de registro | `2026-11-21` |

## Uso previsto

Detección de personas en frames BGR `uint8` de forma `H x W x 3` dentro del pipeline de
Vision Core. Solo se consumen las cajas de la clase COCO 0 (`person`) con confianza
configurada en `0.5`; el tracker local asigna `track_id`.

## Fuera de uso

No se usa para reconocimiento de identidad, detección de otras clases, conteo certificado
de aforo, vigilancia normativa ni video con personas menores de edad sin evaluación de
privacidad. No está validado con grabaciones reales de la sala.

## Datos de entrenamiento o proveniencia conocida

Pesos preentrenados de YOLOv8n sobre COCO, distribuidos por Ultralytics y cargados con
`YOLO("yolov8n.pt")`. La revisión concreta del archivo no está fijada: la biblioteca
descarga la versión disponible en el momento del primer uso. Fuente consultada el
`2026-11-21`: <https://docs.ultralytics.com/models/yolov8/>.

## Métricas del ticket 36

| Métrica | Valor | Origen |
|---|---:|---|
| mAP val 50-95 publicado (COCO, 640 px) | 37.3 | Documentación oficial Ultralytics |
| FPS de procesamiento completo (sintético, 35 frames) | 15.89 | `reports/synthetic-performance.json` |
| FPS del pipeline (sintético, 35 frames) | 5.55 | `reports/synthetic-performance.json` |
| Tiempo por frame p50 / p95 / p99 | 59.49 / 69.70 / 131.89 ms | `reports/synthetic-performance.json` |
| Precisión, recall y latencia captura → evento | No medidos | Sin ground truth anotado |

La medición local usó un video sintético que desplaza `bus.jpg`, sin calentamiento ni
anotaciones humanas; no es un benchmark estable ni evidencia de precisión en la sala.

## Limitaciones y sesgos conocidos

- Rendimiento y precisión no certificados en condiciones reales de iluminación, aforo u
  oclusiones; ver `reports/room-evaluation.md`.
- El detector hereda limitaciones de COCO y del tamaño de entrada; personas pequeñas o
  parcialmente visibles pueden omitirse.
- `artifact_version: unpinned` y `checksum: null`: no hay reproducibilidad byte a byte
  hasta fijar el archivo y registrar su SHA-256.
- Los umbrales no se ajustaron con base en el video sintético.

## Dependencias y licencias

| Componente | Versión declarada | Licencia |
|---|---|---|
| `ultralytics` | `8.4.201` en `requirements.txt` | AGPL-3.0 o Enterprise |
| Pesos `yolov8n.pt` | Sin fijar | AGPL-3.0 por defecto según Ultralytics |
| `torch` / `opencv-python` | Ver `requirements*.txt` | Según paquetes |

La licencia AGPL-3.0 puede obligar a publicar el trabajo derivado; para despliegue
privado o comercial revisar la licencia Enterprise con el ticket 42.

## Configuración esperada

`VISION_CORE_DETECTION_MODEL_ID=detection.person.yolov8n`,
`VISION_CORE_MODEL_PATH=yolov8n.pt`, `VISION_CORE_DETECTION_CONFIDENCE=0.5`,
`VISION_CORE_DETECTION_CLASSES=0`. El arranque rechaza cualquier desviación.

## Procedimiento de rollback

1. Restaurar el archivo `yolov8n.pt` de la versión anterior y su ruta exacta.
2. Volver a fijar `VISION_CORE_DETECTION_MODEL_ID=detection.person.yolov8n` y la entrada
   anterior del registro si se había adoptado una versión nueva.
3. Reiniciar y comprobar `detection.model_id`, `model_version` y `model_hash` en `/ready`.

## Verificación

`python -m vision_core.scripts.validate_pipeline --video ... --zones ...` sigue el
protocolo de `docs/validation.md`. Para comparar variantes del mismo modelo base, ver
`docs/model-registry.md` y el ticket 56.
