# Reporte de hotspots (baseline sintético)

Generado con `synthetic-cpu-320x240`, 450 frames a 320x240, detector
`SyntheticDetector` y pipeline real. Los valores son del baseline local de
referencia; el hardware del runner y el modelo Real pueden cambiar el orden.

| Métrica | Valor | Presupuesto | Estado |
|---|---:|---:|---|
| FPS | 274.47 | >= 30.0 | OK |
| Frame p50 (ms) | 1.76 | <= 33.3 | OK |
| Frame p95 (ms) | 3.03 | <= 60.0 | OK |
| Inferencia p50 (ms) | 0.77 | <= 20.0 | OK |
| Inferencia p95 (ms) | 1.22 | <= 40.0 | OK |
| Memoria pico (MB) | 0.67 | <= 512.0 | OK |
| Crecimiento memoria (MB/h) | 28.20 | <= 1024.0 | OK |
| Arranque a primer frame (ms) | 21.43 | <= 8000.0 | OK |
| Reconexión (ms) | 0.11 | <= 3000.0 | OK |

## Hotspots por p95

- captura/decode: p95 1.942 ms, max 33.908 ms
- detección: p95 1.224 ms, max 8.960 ms
- serialización: p95 0.598 ms, max 0.777 ms
- tracking/ReID: p95 0.284 ms, max 1.718 ms
- puerta/zonas: p95 0.262 ms, max 1.364 ms
- embedding ReID: p95 0.034 ms, max 0.133 ms

## Interpretación

- La captura incluye `cv2.VideoCapture.read()` y la validación del frame; en un
  streaming RTSP real puede dominar por red y códec.
- La detección con el detector sintético mide el escaneo de marcas y la
  construcción de `Detection`. Con YOLO real, sustituye el cuello de botella y
  obliga a regenerar baseline y presupuestos.
- La serialización aparece porque el benchmark llama a `event_to_json` por
  evento, igual que el monitor; solo se ejecuta cuando hay eventos de puerta.
- ReID, tracking y zonas son baratos con una persona. Crecerán con el número de
  tracks simultáneos; la matriz multi-cámara está fuera de alcance.
- El pico de memoria se mide con `tracemalloc` en Windows. En Linux se prefiere
  `VmHWM` de `/proc/self/status`; el campo `source` del JSON lo indica.

Consulta [presupuestos, metodología y comandos](../docs/performance.md).
