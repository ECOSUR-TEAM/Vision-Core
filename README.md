# Vision Core

Pipeline de analítica de personas: **cámara → Frigate/go2rtc → RTSP → YOLOv8 y
tracking → embeddings y ReID → zonas → eventos JSON**. La ejecución no usa navegador
ni Internet Explorer. Frigate entrega video; Vision Core hace su propia detección.

La integración se probó con capturas simuladas y video sintético con modelos reales.
La calibración y aceptación con la Vivotek de la sala quedan pendientes hasta tener
la cámara. No se conoce aún su modelo ni su ruta RTSP.

## Instalación local (Linux, Bash)

El proyecto declara Python ≥3.10; para una instalación nueva usa Python 3.11 o
posterior compatible con las versiones de PyTorch/torchvision instaladas. El
Dockerfile utiliza Python 3.11. CPU es suficiente para las pruebas; GPU es opcional.

```bash
git clone https://github.com/ECOSUR-TEAM/Vision-Core vision-core
cd vision-core
sudo apt-get update
sudo apt-get install -y python3-venv ffmpeg libgl1 libglib2.0-0
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check
python -m pytest -q
```

Si ya tienes el repositorio, comienza en su carpeta. `ffprobe` viene con FFmpeg y
se necesita para inspeccionar códec/transporte. OpenCV utiliza su backend FFmpeg
para decodificar; `ffprobe` por sí solo no garantiza ese backend.

Para CUDA, instala la pareja torch/torchvision adecuada al driver siguiendo el
[selector oficial de PyTorch](https://pytorch.org/get-started/locally/), antes de
instalar el resto de requirements. Comprueba el entorno:

```bash
python -c "import torch, torchvision, cv2; print(torch.__version__, torchvision.__version__, cv2.__version__); print('CUDA disponible:', torch.cuda.is_available())"
```

`requirements.txt` no fija versiones. Conserva `python -m pip freeze` con cada
medición para reproducirla. No se requiere OSNet, torchreid ni `third_party/`.

## Primera prueba sin cámara

```bash
python -m scripts.create_pipeline_sample /tmp/vision-core-demo
VISION_CORE_EMBEDDING_DEVICE=cpu python -m scripts.validate_pipeline \
  --video /tmp/vision-core-demo/sample.avi \
  --zones /tmp/vision-core-demo/zones.json \
  --output /tmp/vision-core-demo/result.jsonl
```

Usa un directorio nuevo y un archivo de salida nuevo. La demo desplaza una imagen
de ejemplo; no representa condiciones reales de la sala. YOLO usa `yolov8n.pt` y
el extractor descarga sus pesos torchvision si no están en caché: el primer uso
requiere red. Prepara los pesos previamente para un despliegue sin internet.
El archivo JSONL incluye detecciones, tracks, identidades resueltas, eventos y métricas.

## Frigate y ejecución con cámara

1. Configura el restream siguiendo [la guía de Frigate](docs/frigate.md).
2. Copia el ejemplo y edita los valores de tu entorno:

```bash
cp .env.example .env
# Editar .env antes de continuar; no publicar credenciales.
set -a
source .env
set +a
python -m infrastructure.video.check_stream --frames 100 --transport tcp
```

Python no carga `.env` automáticamente: `source` exporta sus valores. Docker
Compose sí carga el archivo mediante `env_file`. Mantén las comillas en valores
con `;`, `&`, `#` u otros caracteres especiales.

3. Captura una imagen y calibra los polígonos:

```bash
python -m infrastructure.video.capture_reference referencia.png
cp config/zones.example.json config/zones.json
# Editar frame_size, door, exterior e interior usando referencia.png.
python -m infrastructure.door.check_zones referencia.png config/zones.json zonas.png
```

El ejemplo contiene coordenadas sintéticas. La [guía de calibración](docs/validation.md#calibrar-puerta-y-zonas-con-la-cámara)
explica los ejes, bordes y prioridades. No cambies resolución ni encuadre después
de calibrar. La aplicación falla si el tamaño del frame difiere de `frame_size`.

4. Con `.env` cargado y zonas revisadas:

```bash
python main.py
```

Los eventos se imprimen como JSON en stdout; los diagnósticos de bibliotecas pueden
compartir esa salida. Para un registro estructurado de pruebas usa el runner:

```bash
python -m scripts.validate_pipeline --zones config/zones.json --frames 3000 --output sala.jsonl
```

Omitir `--video` selecciona RTSP. Ctrl+C cierra el stream. Tras agotar reintentos el
proceso termina con error; no hay supervisor ni reinicio automático.

## Variables de entorno

| Variable | Predeterminado | Uso |
|---|---|---|
| `VISION_CORE_RTSP_URL` | Obligatoria para RTSP | `rtsp://HOST_FRIGATE:8554/NOMBRE_STREAM` |
| `VISION_CORE_OPEN_TIMEOUT_MS` | `5000` | Timeout positivo por apertura |
| `VISION_CORE_READ_TIMEOUT_MS` | `5000` | Timeout positivo por lectura |
| `VISION_CORE_RECONNECT_ATTEMPTS` | `5` | Reintentos; `0` los desactiva |
| `VISION_CORE_RECONNECT_DELAY_SECONDS` | `2` | Espera no negativa entre reintentos |
| `OPENCV_FFMPEG_CAPTURE_OPTIONS` | Sin valor propio en código | Ejemplo: `'rtsp_transport;tcp'`; global al proceso |
| `VISION_CORE_ZONES_FILE` | Obligatoria en `main.py` | Ruta al JSON de calibración |
| `VISION_CORE_ZONE_CONFIRMATION_FRAMES` | `3` | Observaciones consecutivas para confirmar zona en `main.py` |
| `VISION_CORE_EMBEDDING_MODEL` | `mobilenet_v3_small` | También admite `resnet50` |
| `VISION_CORE_EMBEDDING_DEVICE` | CUDA si está disponible; si no CPU | `cpu`, `cuda`, `cuda:0`; CUDA explícita falla si no está disponible |
| `DETECTION_TEST_VIDEO` | Ausente | Video local para prueba optativa de detección real (≥30 s, personas visibles) |
| `DETECTION_TEST_MODEL` | Ausente | Pesos locales para esa prueba optativa |

El runner recibe zonas por `--zones` y pesos YOLO por `--model`; usa confirmación de
3 observaciones y no lee `VISION_CORE_ZONE_CONFIRMATION_FRAMES`. `check_stream`
fija transporte con `--transport`, sustituyendo las opciones FFmpeg del proceso.
`main.py` usa `yolov8n.pt`; no hay variable de modelo YOLO ni de dispositivo YOLO.
La variable del extractor solo controla el extractor.

Parámetros de código, no variables: confianza de persona **>0.5**, IoU mínimo
**0.3**, expiración tras **31** frames ausentes (tolera 30), TTL ReID **60 s** desde
la pérdida, similitud coseno **>0.85**, historial de zonas **300** observaciones por
persona. El TTL usa tiempo monotónico; los eventos llevan timestamp Unix.

## Docker

Después de crear `.env` y calibrar `config/zones.json`:

```bash
docker compose up --build
docker compose logs -f vision-core
# En otra terminal, para detener:
docker compose down
```

El Compose incluido levanta **solo Vision Core**, no Frigate. Usa una IP del
servidor Frigate accesible desde el contenedor; `localhost` señala al propio
contenedor. El código se monta en `/app`, por eso `config/zones.json` funciona
como ruta relativa. Este Compose no configura GPU: usa CPU o prepara explícitamente
el runtime NVIDIA antes de solicitar CUDA. La imagen actual no instala el ejecutable
`ffprobe`; ejecuta el diagnóstico de códec en el host con FFmpeg instalado.
Los pesos torchvision descargados dentro del contenedor no tienen volumen de caché
persistente configurado. La construcción Docker no se ha certificado en esta sesión.

## Módulos y responsabilidades

| Componente | Responsabilidad |
|---|---|
| `domain/entities.py` | Bounding boxes, detecciones, polígonos y eventos |
| `domain/ports/` | Contratos de video, detector/tracker, ReID y zonas |
| `infrastructure/video/` | RTSP con reconexión, reproducción de archivos, validación BGR y captura de referencia |
| `infrastructure/detection/` | YOLOv8, personas clase COCO 0, cajas en píxeles y tracking local por movimiento/IoU |
| `infrastructure/reid/` | Recortes BGR→RGB, embeddings L2 y recuperación temporal de `person_id` |
| `infrastructure/door/` | Validación de polígonos, zona por centro del bbox, confirmación e historial |
| `application/vision_core_app.py` | Orquestación, notificación de pérdidas, mappings, eventos y cierre |
| `main.py` | Construcción e inyección de las implementaciones concretas |
| `scripts/` | Demo sintética, ejecución medida y evaluación contra anotaciones |

La aplicación depende de los ports, no de infraestructura. Los adaptadores no
importan otras carpetas de infraestructura; los puntos de composición conectan
los módulos. Dueños originales: detección Carlos/Ameth, ReID Briyan, zonas Melissa,
orquestación Fabricio.

## Pruebas y documentación de referencia

```bash
python -m pytest -q
python -m pytest tests/integration tests/application -q
DETECTION_TEST_VIDEO=/ruta/video.avi DETECTION_TEST_MODEL=/ruta/yolov8n.pt python -m pytest tests/infrastructure/detection/test_real_video.py -q
python -m scripts.evaluate_room sala.jsonl anotaciones.json
```

Los tests no descargan pesos. Se omiten pruebas reales cuando falta video, pesos
locales o CUDA; una omisión no es una validación. La suite mezcla pruebas unitarias,
escenas controladas y pruebas reales optativas. Consulta:

- [Calibración, stream, eventos y pruebas](docs/validation.md).
- [Orquestación y cierre](application/README.md).
- [Detección y tracking](infrastructure/detection/README.md).
- [Embeddings y TTL](infrastructure/reid/README.md).
- [Resultados, anotaciones y evaluación pendiente de la sala](reports/room-evaluation.md).
- [Hardware y problemas conocidos](docs/operations.md).

Con la cámara disponible: confirmar modelo/ruta RTSP, capturar referencia, calibrar
zonas y ejecutar la evaluación de la sala. No hay aún cifras certificadas de precisión,
latencia de captura, capacidad máxima ni continuidad de identidades en esa cámara.
