# Detección y seguimiento

`YoloDetectorManager.process(frame)` devuelve `list[Detection]` con personas
(clase COCO 0) cuya confianza es estrictamente mayor que 0.5.

Reutiliza una instancia por video y procesa sus frames en orden. El tracker
propio asocia cajas por IoU (mínimo 0.3), predice su movimiento con velocidad
constante y asigna IDs locales crecientes. Conserva las trayectorias durante
30 frames sin detección; no devuelve cajas predichas durante esas ausencias.
Una instancia nueva inicia un seguimiento independiente.

No requiere dependencias adicionales. No implementa ReID ni el algoritmo
ByteTrack completo: movimientos bruscos, cambios de cámara y solapamientos
ambiguos pueden cambiar los IDs.

Pruebas: `pytest tests/infrastructure/test_yolo_detector_manager.py`.
Cubren filtros, movimiento, cruces, orden variable, ausencias y expiración.
Para validar un video real, usa una única instancia durante todo el video y
comprueba los IDs devueltos junto a cada caja; las pruebas usan salidas YOLO
simuladas y no sustituyen esa validación visual.

## FPS sobre video real

Medición del 2026-09-22: **59.16 FPS promedio de detección + tracking**;
**56.60 FPS incluyendo decodificación**. Se procesaron los primeros **30 segundos
continuos (300 frames)** de `vtest.avi`: 768×576, 10 FPS de origen, duración total
79.5 s. Resultado: 1,817 detecciones de personas, 5.071 s dentro de `process()`
y 5.301 s incluyendo lectura. Una ejecución en CPU AMD Ryzen 9 8940HX,
Linux x86_64, YOLOv8n con parámetros de inferencia predeterminados.

Entorno: Python 3.14.4, Ultralytics 8.4.159, PyTorch 2.14.0+cpu, OpenCV 5.0.0,
NumPy 2.5.3. No se utilizó GPU. Los FPS dependen del equipo y de la escena.

Método: `frames / suma del tiempo de process()`, medido con `perf_counter`.
Incluye preprocesamiento, inferencia, filtrado, tracking y la primera inferencia
en frío; excluye carga del modelo, descargas y visualización. La segunda cifra
incluye también lectura/decodificación. No se saltan ni repiten frames, no hay
calentamiento previo y no se redimensionan antes de llamar a `process()`.

### Reproducir

Desde la raíz del proyecto, con `requirements.txt` instalado:

```bash
mkdir -p /tmp/vision-core-detection-assets
curl -fL https://raw.githubusercontent.com/opencv/opencv/4.12.0/samples/data/vtest.avi -o /tmp/vision-core-detection-assets/vtest.avi
curl -fL https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt -o /tmp/vision-core-detection-assets/yolov8n.pt
python -m infrastructure.detection.benchmark /tmp/vision-core-detection-assets/vtest.avi --model /tmp/vision-core-detection-assets/yolov8n.pt --seconds 30 --output /tmp/vision-core-detection-assets/benchmark.json
DETECTION_TEST_VIDEO=/tmp/vision-core-detection-assets/vtest.avi DETECTION_TEST_MODEL=/tmp/vision-core-detection-assets/yolov8n.pt pytest -q
```

Fuente: [video de prueba de OpenCV 4.12.0](https://github.com/opencv/opencv/blob/4.12.0/samples/data/vtest.avi).
SHA-256 del video: `45cddc9490be69345cbdab64ca583be65987e864ca408038e648db99e10516cf`.
SHA-256 de los pesos: `f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36`.

El test en `tests/infrastructure/detection/test_real_video.py` ejecuta `process()`
real sobre los 300 frames, verifica el contrato, cajas válidas, IDs únicos por
frame y reutilización de IDs entre frames. No impone un FPS mínimo ni demuestra
ausencia de cambios de identidad. Sin las dos variables de entorno se omite
explícitamente; con rutas inválidas o video insuficiente falla. Los archivos
multimedia y pesos se descargan explícitamente, nunca durante pytest.

Validación con video y pesos locales: **8 tests passed**, sin tests omitidos
(suite completa, incluyendo integración real y rechazo de video corto).
