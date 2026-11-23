# Configuracion tipada

La configuracion se normaliza y valida con `vision_core.core.config.Settings.from_env()`.
El composition root carga `Settings` al arranque y pasa esos valores a los adaptadores;
los puntos de entrada heredados pueden reconstruir su seccion con `validate_startup=False`
para no exigir archivos o URLs presentes solo en despliegues completos.
Todas las variables se convierten a tipos Python y se validan antes de construir la aplicacion.
Los valores invalidos producen `SettingsError` con la variable exacta y una accion correctiva.
La decision esta registrada en el [ADR 0004](adr/0004-configuracion-tipada-y-validacion-de-entorno.md).

## Variables

### Video y RTSP

| Variable | Predeterminado | Validacion |
|---|---|---|
| `VISION_CORE_VIDEO_SOURCE` | `rtsp` | `rtsp` o `file` |
| `VISION_CORE_RTSP_URL` | Ninguno | Obligatoria para RTSP; URL `rtsp://` o `rtsps://` |
| `VISION_CORE_VIDEO_PATH` | Ninguno | Obligatorio para archivo; ruta existente |
| `VISION_CORE_RTSP_TRANSPORT` | `tcp` | `tcp` o `udp` |
| `VISION_CORE_OPEN_TIMEOUT_MS` | `5000` | Entero positivo |
| `VISION_CORE_READ_TIMEOUT_MS` | `5000` | Entero positivo |
| `VISION_CORE_RECONNECT_ATTEMPTS` | `5` | Entero no negativo |
| `VISION_CORE_RECONNECT_DELAY_SECONDS` | `2` | Numero finito no negativo |
| `VISION_CORE_DECODER_THREADS` | `1` | Entero no negativo |
| `OPENCV_FFMPEG_CAPTURE_OPTIONS` | Ninguno | Opciones globales de OpenCV/FFmpeg |

### Registro de modelos

| Variable | Predeterminado | Validacion |
|---|---|---|
| `VISION_CORE_MODEL_REGISTRY_FILE` | `config/models.yml` | YAML versionado debe existir al arranque |
| `VISION_CORE_DETECTION_MODEL_ID` | `detection.person.yolov8n` | ID presente, activo y de tarea `detection` |
| `VISION_CORE_EMBEDDING_MODEL_ID` | `embedding.person.mobilenet_v3_small` | ID presente, activo y de tarea `embedding` |
| `VISION_CORE_MODEL_CHECKSUM_VERIFY` | `1` | Booleano: exige y compara checksum declarado; falla si falta el archivo |

El registro es texto (`config/models.yml`), no una base de datos ni un servidor de modelos.
Si el `model_id` no existe, el arranque termina con `ConfigurationError` antes de abrir el stream.
Si el checksum registrado no es `null` y el archivo local existe, un desajuste también detiene el arranque.

### Deteccion

| Variable | Predeterminado | Validacion |
|---|---|---|
| `VISION_CORE_MODEL_PATH` | `yolov8n.pt` | Archivo existente |
| `VISION_CORE_DETECTION_DEVICE` | `cpu` | `cpu`, `cuda` o `cuda:<indice>` |
| `VISION_CORE_DETECTION_CONFIDENCE` | `0.5` | Mayor que 0 y menor o igual a 1 |
| `VISION_CORE_DETECTION_CLASSES` | `0` | Clases COCO separadas por comas |
| `VISION_CORE_TRACKING_ENABLED` | `1` | Booleano |
| `VISION_CORE_TRACK_MAX_MISSED_FRAMES` | `30` | Entero positivo |

### ReID

| Variable | Predeterminado | Validacion |
|---|---|---|
| `VISION_CORE_EMBEDDING_MODEL` | `mobilenet_v3_small` | Modelo soportado |
| `VISION_CORE_EMBEDDING_WEIGHTS` | `DEFAULT` | Perfil de pesos declarado en el registro |
| `VISION_CORE_EMBEDDING_DEVICE` | Automatico | `cpu`, `cuda` o `cuda:<indice>` |
| `VISION_CORE_REID_THRESHOLD` | `0.85` | Mayor que 0 y menor o igual a 1 |
| `VISION_CORE_REID_AMBIGUITY_MARGIN` | `0.03` | Entre 0 y 1 |
| `VISION_CORE_REID_TTL_SECONDS` | `0` | Numero finito no negativo; 0 conserva durante la ejecucion |
| `VISION_CORE_REID_GALLERY_SIZE` | `8` | Entero positivo |

### Zonas y monitor

| Variable | Predeterminado | Validacion |
|---|---|---|
| `VISION_CORE_ZONES_FILE` | Ninguno | Archivo existente si se usan zonas reales |
| `VISION_CORE_ZONE_CONFIRMATION_FRAMES` | `3` | Entero positivo |
| `VISION_CORE_MONITOR_DEMO_ZONES` | `0` | Booleano |
| `VISION_CORE_MONITOR_UNCALIBRATED` | `0` (Compose: `1`) | Booleano |
| `VISION_CORE_MONITOR_HOST` | `127.0.0.1` | Host no vacio |
| `VISION_CORE_MONITOR_PORT` | `8080` | Puerto entre 1 y 65535 |
| `VISION_CORE_MONITOR_EXIT_ON_ERROR` | `0` | Booleano |
| `VISION_CORE_LOG_LEVEL` | `INFO` | Nivel Python admitido |
| `VISION_CORE_LOG_JSON` | `1` | Booleano: `1` para logs JSON |
| `VISION_CORE_CAMERA_ID` | `default` | Identificador estable de la camara |
| `VISION_CORE_MINIMUM_FREE_DISK_MB` | `500` | Entero no negativo |
| `VISION_CORE_DISK_CHECK_PATH` | `.` | Ruta existente para el check de disco |
| `VISION_CORE_PERFORMANCE_INTERVAL_SECONDS` | `1.0` | Numero positivo |

### Calidad de cámara y deriva

Cada variable admite una variante específica por cámara con el prefijo
`VISION_CORE_CAMERA_QUALITY_<CAMERA_ID>_` (por ejemplo,
`VISION_CORE_CAMERA_QUALITY_CAMERA_1_CHECK_BLUR=0`). La variante específica gana
sobre la global. Detalles y acciones en [calidad de cámara](camera-quality.md).

| Variable | Predeterminado | Validacion |
|---|---|---|
| `VISION_CORE_CAMERA_QUALITY_ENABLED` | `1` | Booleano; `0` desactiva el monitor completo |
| `VISION_CORE_CAMERA_QUALITY_SAMPLE_EVERY_N_FRAMES` | `15` | Entero ≥ 1 |
| `VISION_CORE_CAMERA_QUALITY_FROZEN_FRAMES` | `30` | Entero ≥ 2 (muestras consecutivas) |
| `VISION_CORE_CAMERA_QUALITY_FROZEN_DIFFERENCE` | `1.0` | Numero finito no negativo |
| `VISION_CORE_CAMERA_QUALITY_MIN_BLUR_VARIANCE` | `50.0` | Numero finito no negativo |
| `VISION_CORE_CAMERA_QUALITY_MIN_BRIGHTNESS` | `25.0` | `0 <= min < max <= 255` |
| `VISION_CORE_CAMERA_QUALITY_MAX_BRIGHTNESS` | `230.0` | `0 <= min < max <= 255` |
| `VISION_CORE_CAMERA_QUALITY_CHECK_RESOLUTION` | `1` | Booleano |
| `VISION_CORE_CAMERA_QUALITY_CHECK_FROZEN` | `1` | Booleano |
| `VISION_CORE_CAMERA_QUALITY_CHECK_BLUR` | `1` | Booleano |
| `VISION_CORE_CAMERA_QUALITY_CHECK_EXPOSURE` | `1` | Booleano |
| `VISION_CORE_CAMERA_QUALITY_CHECK_ZONES` | `1` | Booleano |

### Render y pipeline

| Variable | Predeterminado | Validacion |
|---|---|---|
| `VISION_CORE_RENDER_ENABLED` | `1` | Booleano; `0` omite render/JPEG (lo fuerza `--no-render`) |
| `VISION_CORE_EMBEDDING_BATCH_SIZE` | `1` | Entero positivo; reservado para batching futuro |
| `VISION_CORE_EMBEDDING_STRIDE` | `1` | Entero positivo; reservado para salto de embeddings |
| `VISION_CORE_PROFILING_ENABLED` | `0` | Booleano; activa timers `perf_counter` |
| `VISION_CORE_PROFILING_OUTPUT` | `profiling_results.json` | Ruta no vacia del informe JSON |

Los booleanos aceptan `1/0`, `true/false`, `yes/no` y `on/off` sin distincion
de mayusculas. Los valores invalidos se rechazan antes de iniciar el pipeline.

### Persistencia y retencion

| Variable | Predeterminado | Validacion |
|---|---|---|
| `VISION_CORE_DB_ENABLED` | `1` si hay `DB_PATH` | Booleano; `0` desactiva la persistencia |
| `VISION_CORE_DB_PATH` | `vision-core.sqlite3` | Ruta del archivo SQLite |
| `VISION_CORE_DB_FAIL_OPEN` | `1` | `1`: la DB falla y el pipeline sigue en memoria |
| `VISION_CORE_DB_BUSY_TIMEOUT_SECONDS` | `5` | Espera ante bloqueos |
| `VISION_CORE_EVENT_TTL_SECONDS` | `2592000` | Retencion de eventos |
| `VISION_CORE_HISTORY_TTL_SECONDS` | `604800` | Retencion de observaciones de zona |
| `VISION_CORE_IDENTITY_TTL_SECONDS` | `86400` | Retencion de identidades |
| `VISION_CORE_TRACK_TTL_SECONDS` | `86400` | Retencion de tracks |
| `VISION_CORE_SESSION_TTL_SECONDS` | `2592000` | Retencion de sesiones |
| `VISION_CORE_METRICS_TTL_SECONDS` | `2592000` | Retencion de metricas |
| `VISION_CORE_DB_PRUNE_INTERVAL_SECONDS` | `3600` | Frecuencia del worker de limpieza |

Un TTL de `0` desactiva el borrado por tiempo de ese tipo. Esta tabla es un
resumen; [persistencia](persistence.md) es la fuente canónica de defaults, TTLs
y backup, con [ADR 0002](adr/0002-persistence-and-retention.md) como decisión.

### Integracion de Frigate

| Variable | Predeterminado | Validacion |
|---|---|---|
| `FRIGATE_CAMERA_RTSP_URL` | Ninguno | URL RTSP valida sin almacenar credenciales reales |
| `FRIGATE_WEBCAM_DEVICE` | `/dev/video0` | Ruta del dispositivo de video |

No registrar ni imprimir URLs ni variables que puedan contener credenciales. Usa
`redact_sensitive()` antes de incluir cualquier URL en texto o reporte.
