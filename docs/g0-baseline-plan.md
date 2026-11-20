# Plan operativo G0: baseline multi-cámara sin cambiar el modelo de ejecución

| Campo | Valor |
|---|---|
| Estado | Ejecutado |
| Fecha | 2026-11-20 |
| Ticket | ECM-80 (prerrequisito G0 de ADR-0003) |
| Relación | No sustituye ni modifica ADR-0003 |

Este documento registra la instrumentación necesaria para comparar el pipeline
antes de cualquier cambio de modelo de ejecución. **No autoriza implementación
multi-cámara**: se mantiene un proceso, una cámara, un `VideoSource`, ReID local
y un único composition root (`main.py`), según `docs/adr/0003-modelo-ejecucion-multi-camara.md`.

## Flujo instrumentado

```mermaid
flowchart LR
    A[VideoSource] --> B[decode]
    B --> C[DetectorManager]
    C --> D[EmbeddingExtractor]
    D --> E[ReIDMemory local]
    E --> F[DoorAnalytics]
    F --> G[EventConsumer / PersistenceService]
    C --> H[on_frame]
    H --> I[LatestFrameBuffer_acotado]
    I --> J[RendererThread]
    J --> K[JPEG]
    K --> L[MonitorState]
    L --> M[/api/v1/state]
    L --> N[/metrics]
    O[FrameProfiler] --> P[profiling_results.json]
```

El buffer es de 1 frame por defecto y admite 2 como máximo. `publish` NUNCA
espera al renderer: si la cola está llena descarta el frame más antiguo y
aumenta `dropped`. El consumidor toma el payload más viejo de la cola.

## Cambios incluidos

- `FrameProfiler` emite `camera_id` en `summary()` y en `profiling_results.json`.
  Las claves anteriores (`frames`, `elapsed_seconds`, `fps`, `stages`) se conservan.
- `VISION_CORE_CAMERA_ID` alimenta logs, estado del monitor, profiling y métricas.
- Las métricas conservan las claves agregadas históricas y añaden una clave
  etiquetada `metrica{camera_id=<id>}` cuando el identificador no es `default`.
- `LatestFrameBuffer(maxsize=1|2)` hace explícito el límite y la política
  drop-old. No se introduce `queue.Queue`, broker ni cola de inferencia nueva.
- `drop-old` se contabiliza en `vision_core_frames_discarded_total` y
  `vision_core_queue_size`; `/api/v1/state` no cambia su contrato.

## Pruebas

| Nivel | Archivo | Qué valida |
|---|---|---|
| Integración (PR) | `tests/integration/test_g0_baseline.py` | 35 frames sintéticos, eventos esperados, cierre limpio y JSON con `camera_id` y p50/p95 por etapa |
| Integración (PR) | `tests/test_renderer_pipeline.py` | buffer de 1 y 2, descarte del más antiguo, productor nunca bloqueado y apagado del renderer |
| E2E (PR) | `tests/e2e/test_monitor_e2e.py` | monitor HTTP real, eventos, personas, zonas, JPEG y métricas etiquetadas |
| E2E pesado (nightly) | `tests/e2e/test_g0_profiling_30s.py` | baseline de al menos 30 s con fuente repetitiva local, sin RTSP/GPU/internet |

Comandos:

```bash
python -m pytest -q -m "not slow"
python -m pytest -q -m slow
python -m pytest -q
G0_PROFILING_ARTIFACT=profiling_results.json python -m pytest -q -m slow
```

El job nightly de `e2e.yml` publica `profiling_results.json` como artefacto
`g0-profiling`. La comparación "antes/después" debe hacerse con la misma
resolución y el mismo `VISION_CORE_CAMERA_ID`.

## Límites conocidos

- No hay workers por cámara, reinicio automático, supervision por cámara ni
  health/readiness agregado: un fallo del pipeline sigue deteniendo el proceso.
- No existe identidad *cross-camera*, batching, inferencia compartida ni broker.
- No se han medido 1, 2 y 4 cámaras: ese plan depende de la confirmación de G1.
- `docker-compose.yml` no define `deploy.resources`, `cpus`, `mem_limit` ni
  `pids_limit`. Los límites se documentarán después de G0/G2 con la fórmula
  `N_max = floor(min(VRAM_libre / VRAM_por_camara, RAM_libre / RSS_por_worker,
  CPU_utiles / CPU_por_camara))` y margen de seguridad del 20–30 %.
- Las estimaciones de RAM/VRAM/CPU del ADR-0003 son hipótesis de planificación,
  no resultados de esta medición.
- `/api/v1/state` mantiene su contrato sin `camera_id`; la dimensión solo está
  en `/metrics` y en el archivo de profiling.
- Los frames que no se procesan antes de un apagado se contabilizan como
  descartes; no se encolan para el próximo arranque.

## Puertas restantes

1. **G0 completado:** esta instrumentación y el baseline nocturno de 30 s.
2. **G1:** confirmación escrita de hardware, número de cámaras y requisito de
   ReID *cross-camera*. Sin esa confirmación se mantiene la Opción A del ADR-0003.
3. **G2/G3/G4:** PoC con dos cámaras, batch y propagación de identidad; todas
   requieren un ADR nuevo que sustituya al ADR-0003 antes de tocar código.
