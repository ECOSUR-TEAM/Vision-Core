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
