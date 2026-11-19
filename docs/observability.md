# Observabilidad

## Endpoints

| Endpoint | Uso | Respuesta |
|---|---|---|
| `/health` | Liveness del proceso | `200` mientras el HTTP server puede atender |
| `/ready` | Configuracion, modelo, fuente de video y disco | `200` cuando todo esta listo; `503` si falla un chequeo |
| `/metrics` | Telemetria JSON equivalente a metricas | Contadores, gauges e histogramas |
| `/api/state` | Estado operativo del monitor | Estado, FPS y eventos existentes |

Ejemplo:

```bash
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/ready
curl http://127.0.0.1:8080/metrics
```

## Logs

Cuando `VISION_CORE_LOG_JSON=1`, los logs son JSON con estos campos:

- `timestamp`, `level`, `service`, `camera_id`
- `event_id`, `person_id`, `duration_ms`, `error_code`
- `message`

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
| `vision_core_errors_total` | counter | Errores de pipeline o estado |
| `vision_core_reconnections_total` | counter | Reconexiones exitosas del stream |
| `vision_core_fps` | gauge | FPS suavizado del monitor |
| `vision_core_active_people` | gauge | Personas actualmente resueltas |
| `vision_core_queue_size` | gauge | Frames pendientes en la cola de captura |
| `vision_core_inference_latency_ms` | histogram | Duracion de inferencia de deteccion |
| `vision_core_reid_latency_ms` | histogram | Duracion de embedding y ReID |
| `vision_core_frame_processing_duration_ms` | histogram | Duracion completa por frame |

Las metricas conservan solo las ultimas 1000 observaciones por histograma. No usan
`person_id`, rutas o URLs como labels.

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

## Variables

- `VISION_CORE_LOG_LEVEL`: `CRITICAL`, `ERROR`, `WARNING`, `INFO` o `DEBUG`
- `VISION_CORE_LOG_JSON`: `1` para JSON; `0` para texto
- `VISION_CORE_CAMERA_ID`: identificador estable de la camara
- `VISION_CORE_MINIMUM_FREE_DISK_MB`: espacio libre minimo para readiness
