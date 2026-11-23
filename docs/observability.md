# Observabilidad

## Endpoints

| Endpoint | Uso | Respuesta |
|---|---|---|
| `/health` | Liveness del proceso | `200` mientras el HTTP server puede atender |
| `/ready` | Configuracion, modelo, fuente de video, disco e identidad de modelos | `200` cuando todo esta listo; `503` si falla un chequeo |
| `/metrics` | Telemetria JSON equivalente a metricas | Contadores, gauges e histogramas |
| `/api/v1/state` | Estado operativo del monitor | Estado, FPS, persistencia y eventos existentes |
| `/api/v1/frame?after=N` | Frame JPEG para el visor | `200` JPEG nuevo · `204` sin imagen nueva · `400` `VALIDATION_FAILED` · `503` `VIDEO_FRAME_PENDING` |
| `/api/v1/zones` | Editor de zonas (`GET`/`PUT`, opcional) | `200` · `403` `ZONE_EDITOR_FORBIDDEN` · `404` `REQUEST_NOT_FOUND` · `413` `VALIDATION_FAILED` · `422` |
| `/api/v1/zones/validate` | Validación sin escritura (opcional) | `200` · `404` · `422` |

Las rutas `/api/state` y `/api/frame` siguen disponibles como alias deprecados;
los clientes nuevos deben usar `/api/v1/*`. Ver [contratos](api-contracts.md).

Ejemplo:

```bash
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/ready
curl http://127.0.0.1:8080/metrics
```

`/ready` conserva `ready`, `checks`, `disk_free_mb` y `minimum_free_disk_mb`, y añade
`model_id`, `model_version`, `model_hash` y `models` con la identidad de deteccion y embedding.
`/health` sigue siendo solo liveness, sin metadata de modelos. `model_hash=unverified` indica
que el checksum no está declarado, está desactivado o no se pudo verificar; solo se muestra
`sha256:<hex>` después de una verificación real contra el archivo local.

## Logs

Cuando `VISION_CORE_LOG_JSON=1`, los logs son JSON con estos campos:

- `timestamp`, `level`, `service`, `camera_id`
- `event_id`, `person_id`, `duration_ms`, `error_code`
- `model_id`, `model_version`, `model_hash`
- `embedding_model_id`, `embedding_model_version`, `embedding_model_hash`
- `message`
- `zone_editor_audit` y `zone_editor_access_denied` (sin token, URL ni payload)

`VISION_CORE_LOG_LEVEL` controla el nivel y `VISION_CORE_CAMERA_ID` identifica la camara.
Los frames, imagenes, embeddings y rutas sensibles no se registran. Las URLs RTSP con
credenciales se redactan antes de emitir texto.

## Catalogo de metricas

| Metrica | Tipo | Significado |
|---|---|---|
| `vision_core_frames_processed_total` | counter | Frames entregados al pipeline |
| `vision_core_frames_discarded_total` | counter | Frames descartados por la captura mas reciente |
| `vision_core_tracks_created_total` | counter | Tracks locales nuevos |
| `vision_core_tracks_lost_total` | counter | Tracks perdidos por el detector |
| `vision_core_events_emitted_total` | counter | Eventos de puerta emitidos |
| `vision_core_errors_total` | counter | Errores de pipeline (se cuentan una sola vez) |
| `vision_core_reconnections_total` | counter | Reconexiones exitosas del stream |
| `vision_core_fps` | gauge | FPS suavizado del monitor |
| `vision_core_active_people` | gauge | Personas actualmente resueltas |
| `vision_core_queue_size` | gauge | Frames pendientes en la cola de captura |
| `vision_core_inference_latency_ms` | histogram | Duracion de inferencia de deteccion |
| `vision_core_reid_latency_ms` | histogram | Duracion de embedding y ReID |
| `vision_core_frame_processing_duration_ms` | histogram | Duracion completa por frame |
| `vision_core_camera_quality_degraded` | gauge | `1` cuando la calidad de camara esta degradada |
| `vision_core_camera_quality_degraded_total` | counter | Transiciones a `degraded` (cambio de motivo) |
| `vision_core_camera_quality_<motivo>_total` | counter | Aparicion de cada motivo de calidad |
| `vision_core_camera_quality_errors_total` | counter | Fallos del analisis de calidad |

Cada histograma conserva una ventana de las ultimas 1000 muestras para `min`, `max` y
`p95`, mientras que `count`, `sum` y `avg` son acumulativos desde el arranque. No usan
`person_id`, rutas o URLs como labels. `vision_core_frames_discarded_total` suma el
delta del acumulado de la captura, no el total en cada frame.

Cuando `VISION_CORE_CAMERA_ID` no es `default`, cada metrica se publica dos veces:
con su nombre historico (agregado) y con el sufijo `{camera_id=<id>}`. Por ejemplo,
`vision_core_frames_discarded_total{camera_id=camera-1}` complementa a
`vision_core_frames_discarded_total` sin romper consumidores anteriores. Los
motivos de calidad son codigos estables documentados en
[calidad de camara](camera-quality.md); no cambian `status` ni `/ready`. Los
caracteres no válidos en `camera_id` se normalizan a `_` en la clave de métrica;
el valor original se conserva en `profiling_results.json` y en logs JSON.

## Diagnostico

### FPS bajo

1. Revisa `vision_core_fps` y `vision_core_frame_processing_duration_ms`.
2. Comprueba CPU/GPU y el dispositivo configurado.
3. Reduce resolucion de entrada o espera de deteccion si el histograma crece.

### Camara caida

1. Consulta `/ready`; `video_source=false` indica que el stream no esta conectado.
2. Revisa `vision_core_reconnections_total` y el log con `error_code`.
3. Verifica la URL RTSP sin exponer credenciales y el transporte TCP/UDP.

### Error de modelo

1. Consulta `/ready`; `model=false` indica que el modelo no termino de cargarse.
2. Busca el log con `level=ERROR` y `error_code`.
3. Verifica `VISION_CORE_MODEL_PATH`, formato del archivo y peso disponible localmente.

## Benchmark

El benchmark nocturno guarda un snapshot de estos contadores e histogramas como
telemetría de apoyo y usa `FrameProfiler` para el gate de presupuestos. El e2e
 con `ObservabilityMetrics` fresco comprueba `vision_core_events_emitted_total` y
`vision_core_inference_latency_ms` a través de `/metrics`. Consulta
[performance.md](performance.md) para las cifras y los hotspots.

Los objetivos operativos se consumen desde estos mismos payloads; consulta
[SLOs y tablero](slo.md) para el mapeo de métricas, errores, alertas y runbooks.

## Variables

- `VISION_CORE_LOG_LEVEL`: `CRITICAL`, `ERROR`, `WARNING`, `INFO` o `DEBUG`
- `VISION_CORE_LOG_JSON`: `1` para JSON; `0` para texto
- `VISION_CORE_CAMERA_ID`: identificador estable de la camara en logs, estado,
  metricas y profiling (baseline G0)
- `VISION_CORE_MINIMUM_FREE_DISK_MB`: espacio libre minimo para readiness
- `VISION_CORE_DISK_CHECK_PATH`: ruta comprobada por readiness (`.` por defecto; `/model-cache` en Compose)
