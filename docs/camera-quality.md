# Calidad de cámara y deriva de calibración

Esta guía describe las señales que Vision Core mide sin detener la inferencia.
El objetivo es avisar de que el frame puede ser poco fiable; **no** sustituye a la
validación de zonas ni genera eventos de puerta falsos.

## Señales

| Motivo (`camera_quality.reason`) | Qué detecta | Cómo se mide |
|---|---|---|
| `RESOLUTION_MISMATCH` | Cambio de resolución del stream | `(ancho, alto)` del frame ≠ `frame_size` de las zonas calibradas |
| `ZONES_STALE` | Zonas desactualizadas o fuera del frame | `frame_size` de zonas ≠ resolución actual, o algún vértice fuera del frame actual |
| `FROZEN_FRAME` | Frame congelado o sin variación | La diferencia media entre miniaturas en escala de grises es ≤ `frozen_difference` durante `frozen_frames` muestras consecutivas |
| `BLURRY_FRAME` | Desenfoque | Varianza de Laplace de la miniatura < `min_blur_variance` |
| `EXPOSURE_OUT_OF_RANGE` | Exposición extrema | Brillo medio de la miniatura fuera de `[min_brightness, max_brightness]` |

Si varias señales están activas, `reason` muestra la primera según la precedencia
`RESOLUTION_MISMATCH`, `ZONES_STALE`, `FROZEN_FRAME`, `BLURRY_FRAME`,
`EXPOSURE_OUT_OF_RANGE`. El objeto `signals` conserva todas las activas.

La medición usa una miniatura de 64 × 64 en escala de grises y se ejecuta en el
hilo del renderer reutilizando su frame copiado. Si el render está desactivado,
se usa un hilo propio con un buffer de tamaño 1 (`drop-old`). `sample_every_n_frames`
define cada cuántos frames se analiza; `frozen_frames` cuenta muestras, no frames
consecutivos del stream. Ninguna señal lanza excepciones al pipeline.

## Configuración

Todas las variables son opcionales. Las variables específicas por cámara tienen
precedencia sobre las globales. El sufijo de cámara se normaliza a mayúsculas y
guiones bajos: `VISION_CORE_CAMERA_QUALITY_CAMERA_1_CHECK_BLUR=0` desactiva el
desenfoque solo cuando `VISION_CORE_CAMERA_ID=camera-1`.

| Variable global | Predeterminado | Significado |
|---|---|---|
| `VISION_CORE_CAMERA_QUALITY_ENABLED` | `1` | Activa o desactiva todo el monitor |
| `VISION_CORE_CAMERA_QUALITY_SAMPLE_EVERY_N_FRAMES` | `15` | Muestreo; entero ≥ 1 |
| `VISION_CORE_CAMERA_QUALITY_FROZEN_FRAMES` | `30` | Muestras consecutivas sin cambio; entero ≥ 2 |
| `VISION_CORE_CAMERA_QUALITY_FROZEN_DIFFERENCE` | `1.0` | Diferencia media máxima; finito ≥ 0 |
| `VISION_CORE_CAMERA_QUALITY_MIN_BLUR_VARIANCE` | `50.0` | Varianza de Laplace mínima; finito ≥ 0 |
| `VISION_CORE_CAMERA_QUALITY_MIN_BRIGHTNESS` | `25.0` | Brillo medio mínimo; 0 ≤ min < max ≤ 255 |
| `VISION_CORE_CAMERA_QUALITY_MAX_BRIGHTNESS` | `230.0` | Brillo medio máximo |
| `VISION_CORE_CAMERA_QUALITY_CHECK_RESOLUTION` | `1` | Activa `RESOLUTION_MISMATCH` |
| `VISION_CORE_CAMERA_QUALITY_CHECK_FROZEN` | `1` | Activa `FROZEN_FRAME` |
| `VISION_CORE_CAMERA_QUALITY_CHECK_BLUR` | `1` | Activa `BLURRY_FRAME` |
| `VISION_CORE_CAMERA_QUALITY_CHECK_EXPOSURE` | `1` | Activa `EXPOSURE_OUT_OF_RANGE` |
| `VISION_CORE_CAMERA_QUALITY_CHECK_ZONES` | `1` | Activa `ZONES_STALE` |

Los umbrales son conservadores: empieza con los valores por defecto y ajústalos
solo con evidencia de la cámara real. Desactiva una señal si el entorno produce
falsos avisos (por ejemplo, escenas estáticas legítimas en `FROZEN_FRAME`).

## Estado, métricas y UI

`/api/v1/state` incorpora `camera_quality` sin alterar `status`: el pipeline
sigue `running` y `/ready` sigue respondiendo `200`. El objeto expone
`status` (`ok` o `degraded`), `reason` y `signals`.

`/metrics` publica:

- `vision_core_camera_quality_degraded` (gauge `1`/`0`).
- `vision_core_camera_quality_degraded_total` (contador de transiciones a degradado).
- `vision_core_camera_quality_<motivo_en_minusculas>_total` (contador por motivo).
- `vision_core_camera_quality_errors_total` (fallos del análisis).

Los cambios de motivo se registran en logs con `camera_id` y `reason`, sin
frames ni imágenes. El monitor muestra un aviso textual no intrusivo; nunca
bloquea el video ni el conteo de personas.

## Interpretación y acciones recomendadas

| Motivo | Acción recomendada |
|---|---|
| `RESOLUTION_MISMATCH` | Restaura la resolución configurada en la cámara/Frigate o recalibra las zonas con la nueva resolución. |
| `ZONES_STALE` | Repite la calibración con [la guía de validación](validation.md); no recalibre automáticamente. |
| `FROZEN_FRAME` | Comprueba alimentación, conexión y stream; reinicia la cámara si el frame sigue quieto. |
| `BLURRY_FRAME` | Ajusta el enfoque o la posición de la cámara; revisa suciedad en la lente. |
| `EXPOSURE_OUT_OF_RANGE` | Corrige iluminación o control automático de ganancia/exposición. |

Mientras el estado es `degraded`, los eventos de puerta se siguen calculando con
la lógica existente: la calidad **no** crea ni suprime `FALSE_ALARM`.

## Verificación

Los ejemplos minimizados están en `tests/fixtures/camera_quality/`. La suite
cubre imágenes buena, borrosa, oscura, congelada y con resolución incorrecta:

```bash
python -m pytest -q tests/features/camera_health
python -m pytest -q
```

La decisión estructural está registrada en
[ADR 0009](adr/0009-calidad-de-camara-no-intrusiva.md).
