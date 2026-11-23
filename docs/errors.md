# Catálogo de errores de Vision Core

Los errores esperados usan la jerarquía definida en
`src/vision_core/core/errors/`. Todas las clases derivan de `VisionCoreError`
y exponen cuatro datos: `code` (estable), `message` (seguro para usuarios),
`retryable` y `context` (depuración, sin secretos). Las clases de dominio no
importan HTTP, frameworks ni infrastructure.

Las clases conservan la compatibilidad con las excepciones Python que usaban
antes (`ValueError`, `ConnectionError`, `RuntimeError`, `FileNotFoundError`),
de modo que los clientes existentes siguen capturando el tipo previo.

## Convenciones

- `code` es una cadena MAYÚSCULA con guiones bajos. Forma parte del contrato.
- `message` nunca incluye excepciones nativas, stack traces, rutas de archivos,
  URLs con credenciales, identificadores de persona ni datos personales.
- `retryable=True` indica que una nueva tentativa, tras corregir la causa o
  esperar, puede tener éxito. `retryable=False` exige intervención o cambios.
- `context` solo acepta claves y valores simples. Se descartan claves que
  sugieran secretos, rutas, URLs o identidades (`password`, `token`, `url`,
  `path`, `person`, etc.) y se recortan cadenas largas.
- El borde HTTP solo publica `code`, `message` y `request_id`. `retryable` y
  `context` se registran con `error.as_dict()` y `exc_info=True`; ver
  [contratos versionados](api-contracts.md).

## Jerarquía

| Clase | Código por defecto | `retryable` | Estado HTTP |
|---|---|---|---|
| `VisionCoreError` | `INTERNAL_ERROR` | no | 500 |
| `ConfigurationError` | `CONFIGURATION_INVALID` | no | 500 |
| `VideoSourceError` | `VIDEO_SOURCE_UNAVAILABLE` | sí | 503 |
| `VideoSourceMissingError` | `VIDEO_SOURCE_MISSING` | no | 500 |
| `VideoSourceStateError` | `VIDEO_SOURCE_STATE` | no | 500 |
| `ModelError` | `MODEL_UNAVAILABLE` | no | 500 |
| `ZoneConfigurationError` | `ZONE_CONFIG_INVALID` | no | 422 |
| `ReIDError` | `REID_MODEL_INVALID` | no | 500 |
| `ReIDModelUnavailableError` | `REID_MODEL_UNAVAILABLE` | no | 500 |
| `PipelineError` | `PIPELINE_FAILED` | no | 500 |
| `ValidationError` | `VALIDATION_FAILED` | no | 400 |

## Códigos estables

| Código | `retryable` | HTTP | Cuándo ocurre |
|---|---|---|---|
| `CONFIGURATION_INVALID` | no | 500 | Falta `VISION_CORE_RTSP_URL` o `VISION_CORE_VIDEO_PATH`; valores numéricos de entorno no convertibles; `VISION_CORE_VIDEO_SOURCE` desconocido; `VISION_CORE_ZONE_CONFIRMATION_FRAMES` no entero; modelo o dispositivo de embeddings no válido; `model_id` desconocido, inactivo o con selector/configuración distinta a `config/models.yml`; discrepancia de checksum local. |
| `VIDEO_SOURCE_UNAVAILABLE` | sí | 503 | RTSP no abre tras los reintentos, se agotan los reintentos de lectura, o no se puede abrir el video grabado. |
| `VIDEO_SOURCE_MISSING` | no | 500 | El archivo configurado con `VISION_CORE_VIDEO_PATH` no existe. |
| `VIDEO_SOURCE_STATE` | no | 500 | `read_frame()` antes de `open()`, o el backend OpenCV no puede garantizar salida BGR. |
| `VIDEO_FRAME_PENDING` | sí | 503 | `/api/v1/frame` solicitado antes de que exista un JPEG publicado. |
| `VIDEO_FRAME_INVALID` | no | 400 | Frame que no es `uint8` BGR, vacío, con resolución distinta a la calibrada, o fallo al codificar/decodificar PNG/JPEG. |
| `MODEL_UNAVAILABLE` | no | 500 | Falta Ultralytics o no se pueden cargar los pesos de detección. |
| `MODEL_INPUT_INVALID` | no | 400 | Frame enviado a YOLO con forma o tipo incorrectos. |
| `ZONE_CONFIG_INVALID` | no | 422 | JSON de zonas ilegible, falta `frame_size` o algún polígono, parámetros de confirmación/historial no positivos. |
| `ZONE_GEOMETRY_INVALID` | no | 422 | Polígono con menos de tres puntos, vértices repetidos, sin área, auto-cruzado o fuera de la imagen. |
| `REID_MODEL_INVALID` | no | 500 | Embedding no finito o de norma cero. |
| `REID_MODEL_UNAVAILABLE` | no | 500 | CUDA solicitado sin disponibilidad o pesos de ReID no cargables. |
| `REID_INPUT_INVALID` | no | 400 | Recorte BGR inválido o embedding no normalizable. |
| `PIPELINE_CALIBRATION_MISMATCH` | no | 409 | La resolución del stream no coincide con la calibración de zonas. |
| `PIPELINE_FAILED` | no | 500 | Fallo de orquestación del pipeline distinto a los anteriores. |
| `ZONE_EDITOR_FORBIDDEN` | no | 403 | Token del editor de zonas ausente o incorrecto al intentar guardar. |
| `VALIDATION_FAILED` | no | 400 | Parámetro `after` inválido, cuerpo HTTP rechazado o caja del detector no finita, sin área o fuera del frame. |
| `REQUEST_NOT_FOUND` | no | 404 | Ruta HTTP desconocida o editor de zonas desactivado. |
| `INTERNAL_ERROR` | no | 500 | Excepción inesperada en un límite; se sustituye por un mensaje genérico. |

Los sinks de eventos reutilizan esta taxonomía sin códigos nuevos: un 5xx,
timeout o fallo de red del webhook es `PipelineError` con
`code=PIPELINE_FAILED` y `retryable=True`; un 4xx es `ValidationError` con
`code=VALIDATION_FAILED` y `retryable=False`. El array `retryable` de la tabla
es el valor por defecto de la clase; una instancia puede refinarlo. El adaptador
MQTT no adopta códigos propios: con el flag activo falla con
`CONFIGURATION_INVALID`. Ver [sinks de eventos](event-sinks.md).

### Motivos de calidad (no errores HTTP)

La detección de calidad de cámara no produce excepciones ni envelopes de error.
Publica motivos estables en `camera_quality.reason`, `/metrics` y logs; `status`
sigue siendo `running` y `/ready` devuelve `200`. Los motivos son
`RESOLUTION_MISMATCH`, `ZONES_STALE`, `FROZEN_FRAME`, `BLURRY_FRAME` y
`EXPOSURE_OUT_OF_RANGE`. Su interpretación está en
[calidad de cámara](camera-quality.md). No se reutilizan los códigos Http de esta
tabla, en particular `PIPELINE_CALIBRATION_MISMATCH` (error duro de resolución).

Los códigos se mantienen aunque cambie la implementación interna. Para retirar
uno: documentar la sustitución, conservarlo al menos una versión menor y
eliminarlo solo en un cambio incompatible anunciado con anticipación.

## Verificación de la taxonomía

- Un error de configuración expone `CONFIGURATION_INVALID`, mensaje seguro y
  estado 500 (sin rutas ni valores de entorno sensibles).
- Una cámara caída expone `VIDEO_SOURCE_UNAVAILABLE`, `retryable=True` y 503.
- Los eventos serializados incluyen `schema_version`.
- Los tests de contrato ejercitan fakes y adaptadores reales con dependencias
  externas inyectadas (modelo YOLO simulado, `VideoCapture` simulado y URL RTSP
  sin conexión); no requieren cámara, GPU ni red.
