# Vision Core

## Quickstart

```bash
git clone https://github.com/ECOSUR-TEAM/Vision-Core
cd vision-core
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest
```

## Arquitectura

```
domain/           entidades + ports (contratos), sin dependencias externas
application/      VisionCoreApp: orquesta el pipeline usando solo los ports
infrastructure/   implementaciones concretas (una carpeta por módulo/dueño)
main.py           entrypoint
tests/            un espejo de domain/ y application/
```

Regla: nada en `infrastructure/` importa de otra carpeta de `infrastructure/`.
Todo pasa por los ports en `domain/ports/`.

El orquestador (`application/vision_core_app.py`) mantiene el mapeo
`track_id local -> person_id` y, cuando `DetectorManager.pop_lost_track_ids()`
reporta que un track expiró, llama `ReIDMemory.mark_lost(...)` con su último
embedding. Sin esto, el TTL/similitud coseno de ReIDMemory nunca se dispara
en el pipeline real — ver `infrastructure/detection/README.md`.

## Módulos y dueños (Sprint 1)

| Carpeta | Port | Epic | Dueño(s) |
|---|---|---|---|
| `infrastructure/detection/` | `DetectorManager` | VC-DETECT | Carlos, Ameth |
| `infrastructure/reid/` | `ReIDMemory` | VC-REID | Briyan |
| `infrastructure/door/` | `DoorAnalytics` | VC-DOORLOGIC | Melissa |
| `application/vision_core_app.py` | — | VC-APP | Fabricio |

Cada quien trabaja solo en su carpeta → branch `feature/<módulo>` → PR revisado
por alguien que no sea el dueño.

## Embedder de ReID

`infrastructure/reid/embedder.py` → `TorchvisionEmbeddingExtractor`
(ResNet50 o MobileNetV3-Small de torchvision, sin repos externos ni pesos
aparte). Es el único embedder soportado; no se usa OSNet/torchreid.

Cada módulo documenta su propio README corto dentro de su carpeta al cerrarlo.

## Video RTSP desde Frigate

El recorrido es cámara → Frigate/go2rtc → `RtspVideoSource` → frames BGR del
pipeline. No depende de la interfaz web antigua ni de Internet Explorer.
Frigate debe estar instalado y tener configurado un stream go2rtc accesible:
este repositorio no instala Frigate ni descubre la ruta RTSP de la cámara.

1. Copia `.env.example` a `.env`.
2. Cambia `VISION_CORE_RTSP_URL` a `rtsp://IP_DE_FRIGATE:8554/NOMBRE_DEL_STREAM`.
   El nombre debe coincidir exactamente con el configurado en go2rtc.
   Si Frigate protege el restream, usa sus credenciales en
   `rtsp://usuario:contraseña@IP_DE_FRIGATE:8554/NOMBRE_DEL_STREAM`
   (codifica los caracteres especiales del usuario y contraseña como URL).
3. Ejecuta `docker compose up --build`, o carga las variables para ejecución local:

```bash
set -a
source .env
set +a
python main.py
```

Para `source .env`, coloca entre comillas simples el valor de
`OPENCV_FFMPEG_CAPTURE_OPTIONS='rtsp_transport;tcp'` y cualquier URL que contenga
caracteres especiales. Docker Compose admite esas mismas comillas.

El puerto TCP 8554 debe ser accesible desde Vision Core. Si ambos servicios están
en contenedores, usa la IP del servidor Frigate o un nombre DNS de una red Docker
compartida; `localhost` dentro de Vision Core identifica su propio contenedor.
Consulta la [documentación oficial del restream de Frigate](https://docs.frigate.video/configuration/restream/).

Si Frigate ya entrega video, solo cambia su IP y el nombre del stream. Si aún falta
conectar la Vivotek a Frigate, se necesitan la ruta RTSP, el puerto y las credenciales
correspondientes al modelo. También se puede usar una URL RTSP directa de la cámara;
no se presupone una ruta universal para Vivotek.

| Variable | Valor inicial | Función |
|---|---|---|
| `VISION_CORE_RTSP_URL` | Obligatoria | URL del restream o cámara |
| `VISION_CORE_OPEN_TIMEOUT_MS` | `5000` | Tiempo máximo por apertura |
| `VISION_CORE_READ_TIMEOUT_MS` | `5000` | Tiempo máximo por lectura |
| `VISION_CORE_RECONNECT_ATTEMPTS` | `5` | Reintentos después del fallo; `0` los desactiva |
| `VISION_CORE_RECONNECT_DELAY_SECONDS` | `2` | Pausa entre reintentos |
| `OPENCV_FFMPEG_CAPTURE_OPTIONS` | `rtsp_transport;tcp` en el ejemplo | Transporte FFmpeg, global al proceso |

Se requiere OpenCV con backend FFmpeg y soporte de timeouts. Un fallo de lectura
reabre la conexión y busca un frame válido. Al agotar los reintentos se lanza
`ConnectionError`; no se confunde un corte de red con el fin normal de un video.
`close()` es idempotente y el pipeline lo ejecuta incluso si falla la apertura.
Los mensajes propios omiten la URL; los diagnósticos nativos de FFmpeg pueden
mostrar información del endpoint, por lo que no deben compartirse sin revisión.

### Comprobar solo la ingesta

Después de cargar las variables, este comando recibe un frame sin ejecutar YOLO
ni el embedder ReID (este último sigue pendiente en `main.py`):

```bash
python - <<'PY'
from infrastructure.video.rtsp_video_source import RtspVideoSource
video = RtspVideoSource.from_env()
try:
    video.open()
    frame = video.read_frame()
    print('Frame BGR recibido:', frame.shape)
finally:
    video.close()
PY
```

Pruebas sin cámara: `python -m pytest -q`. Usan capturas simuladas para comprobar
apertura, timeouts enviados al backend, recuperación, agotamiento y liberación.
La conectividad, autenticación y decodificación reales quedan pendientes hasta
disponer de Frigate y la cámara.
