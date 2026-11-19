# Configuracion tipada

La configuracion se carga una sola vez al arranque con `vision_core.settings.Settings.from_env()`.
Todas las variables se convierten a tipos Python y se validan antes de construir la aplicacion.
Los valores invalidos producen `SettingsError` con la variable exacta y una accion correctiva.

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

### Deteccion

| Variable | Predeterminado | Validacion |
|---|---|---|
| `VISION_CORE_MODEL_PATH` | `yolov8n.pt` | Archivo existente |
| `VISION_CORE_DETECTION_DEVICE` | Automatico | `cpu`, `cuda` o `cuda:<indice>` |
| `VISION_CORE_DETECTION_CONFIDENCE` | `0.5` | Mayor que 0 y menor o igual a 1 |
| `VISION_CORE_DETECTION_CLASSES` | `0` | Clases COCO separadas por comas |
| `VISION_CORE_TRACKING_ENABLED` | `1` | Booleano |
| `VISION_CORE_TRACK_MAX_MISSED_FRAMES` | `30` | Entero positivo |

### ReID

| Variable | Predeterminado | Validacion |
|---|---|---|
| `VISION_CORE_EMBEDDING_MODEL` | `mobilenet_v3_small` | Modelo soportado |
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
| `VISION_CORE_MONITOR_UNCALIBRATED` | `0` | Booleano |
| `VISION_CORE_MONITOR_HOST` | `127.0.0.1` | Host no vacio |
| `VISION_CORE_MONITOR_PORT` | `8080` | Puerto entre 1 y 65535 |
| `VISION_CORE_MONITOR_EXIT_ON_ERROR` | `0` | Booleano |
| `VISION_CORE_LOG_LEVEL` | `INFO` | Nivel Python admitido |
| `VISION_CORE_PERFORMANCE_INTERVAL_SECONDS` | `1.0` | Numero positivo |

### Integracion de Frigate

| Variable | Predeterminado | Validacion |
|---|---|---|
| `FRIGATE_CAMERA_RTSP_URL` | Ninguno | URL RTSP valida sin almacenar credenciales reales |
| `FRIGATE_WEBCAM_DEVICE` | `/dev/video0` | Ruta del dispositivo de video |

No registrar ni imprimir URLs ni variables que puedan contener credenciales. Usa
`redact_sensitive()` antes de incluir cualquier URL en texto o reporte.
