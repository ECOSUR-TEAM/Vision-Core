# Detección y seguimiento

`person_detector_from_env()` construye el detector configurado. Por defecto usa
`PosePersonDetectorManager` con `yolov8n-pose.pt`: además de la caja de persona,
exige al menos `VISION_CORE_MIN_VISIBLE_KEYPOINTS` keypoints con confianza
`>= VISION_CORE_KEYPOINT_CONFIDENCE` y al menos una cadera visible (índices
11/12 de COCO). Ese filtro descarta falsos positivos sin esqueleto humano
completo (por ejemplo, un peluche) aunque la caja tenga confianza alta. Si la
caja toca el borde del frame (`FRAME_EDGE_MARGIN`), se acepta la detección
truncada con suficientes keypoints aunque las caderas queden fuera de cuadro.

`YoloDetectorManager.process(frame)` (modo `detect`) devuelve `list[Detection]`
con personas (clase COCO 0) cuya confianza es estrictamente mayor que 0.5.
`PosePersonDetectorManager` hereda el mismo tracker y contrato.

## Configuración

- `VISION_CORE_PERSON_DETECTOR=pose|detect` (por defecto `pose`).
- `VISION_CORE_YOLO_MODEL` (por defecto `yolov8n-pose.pt` en `pose` y
  `yolov8n.pt` en `detect`).
- `VISION_CORE_KEYPOINT_CONFIDENCE` (por defecto `0.5`).
- `VISION_CORE_MIN_VISIBLE_KEYPOINTS` (por defecto `4`).

Reutiliza una instancia por video y procesa sus frames en orden. El tracker
propio asocia cajas por IoU (mínimo 0.3), predice su movimiento con velocidad
constante y asigna IDs locales crecientes. Conserva las trayectorias durante
30 frames sin detección; no devuelve cajas predichas durante esas ausencias.
Una instancia nueva inicia un seguimiento independiente.

## `pop_lost_track_ids()`

Cuando un track supera `MAX_MISSED_FRAMES` sin volver a detectarse, su
`track_id` se elimina internamente y queda en un buffer de "recién perdidos".
`pop_lost_track_ids()` devuelve y **vacía** ese buffer.

Esto existe porque `VisionCoreApp` necesita saber exactamente cuándo un
`track_id` deja de existir para avisarle a `ReIDMemory.mark_lost(...)` al caducar el track. Los IDs crecen y no se reutilizan dentro de una instancia. El orquestador llama
`process()` y luego `pop_lost_track_ids()` en cada frame — nunca al revés,
y nunca se debe usar un `track_id` reportado aquí como si siguiera activo.

Si implementas otro `DetectorManager` (ByteTrack/Norfair reales), tu
implementación debe llevar su propio registro de qué IDs locales caducaron
desde la última llamada y exponerlo igual: no es opcional, es parte del port
(`domain/ports/detector_manager.py`).

No requiere dependencias adicionales. No implementa ReID ni el algoritmo
ByteTrack completo: movimientos bruscos, cambios de cámara y solapamientos
ambiguos pueden cambiar los IDs.

Pruebas: `pytest tests/infrastructure/detection/test_yolo_detector_manager.py`
y `pytest tests/infrastructure/detection/test_pose_person_detector_manager.py`.
Cubren filtros, keypoints, movimiento, cruces, orden variable, ausencias,
expiración y que `pop_lost_track_ids()` reporte cada id perdido exactamente una vez.
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


## Validación de continuidad y ausencias

Las pruebas deterministas pasan detecciones YOLO simuladas por el tracker real:
movimiento horizontal/vertical, giro, pausa, oclusión parcial, reaparición tras
1/29/30 frames, predicción con velocidad, asociaciones competidoras y pérdida
independiente de una persona mientras otra sigue visible.

- IoU usa intersección/unión y compara la detección con la caja predicha. Se
  comprobó geometría, simetría y el umbral: 0.30 asocia; 0.29 no asocia.
- Una detección y un track participan como máximo en una asociación por frame.
- Hasta 30 frames consecutivos sin asociación se conserva el track. Si reaparece
  con IoU suficiente después de esas 30 ausencias, conserva el ID y reinicia el
  contador. En el frame ausente 31 caduca y una aparición posterior recibe otro ID.
- Son frames procesados, no segundos ni frames de la cámara que no llegaron al
  pipeline. Sin llamadas a `process()`, el contador no avanza.
- `pop_lost_track_ids()` acumula las bajas hasta su lectura y vacía el buffer.
  También se verifica que el pipeline avise a ReID exactamente una vez al caducar.

Ejecutar: `python -m pytest -q`. Estas pruebas no acreditan continuidad visual
real en la sala. La asociación espacial puede fallar si la persona reaparece
lejos de la predicción, cambia de dirección oculta o se solapa ambiguamente con
otra. No se modifica el algoritmo para prometer identidad en esos casos.

Para la aceptación con Frigate, grabar una secuencia con una persona caminando,
girando y deteniéndose; después dos personas cruzándose y una ocultándose tras
un objeto. Revisar cajas e IDs frame a frame. Repetir ausencias de 29, 30 y 31
frames procesados, registrar el ID antes/después y el reporte de pérdidas.
Mantener una misma instancia del detector durante toda la secuencia. Los cambios
de identidad deben revisarse contra las personas visibles, no solo contando
IDs repetidos entre frames.
