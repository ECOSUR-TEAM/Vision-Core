# ADR 0009: Calidad de cámara no intrusiva

| Campo | Valor |
|---|---|
| Estado | Propuesta |
| Fecha | 2026-11-22 |
| Tipo | Arquitectura |
| Prioridad | Media |
| Ticket | ECM-100 |
| Etiquetas | `adr`, `camera-health`, `monitor`, `observabilidad` |
| Dependencias | ADR 0001; ADR 0004; ADR 0005; ADR 0008 |
| Impacto | Nuevo slice `camera_health`, campo `camera_quality` en `/api/v1/state`, métricas y aviso visual; el pipeline y los eventos de puerta no cambian. |

## Contexto

Una cámara puede perder enfoque, congelarse, cambiar de resolución o quedar
descalibrada respecto de las zonas marcadas sin que el video deje de llegar.
Ese estado degradado debe hacerse visible al operador y al sistema de
observabilidad, pero no debe detener la inferencia ni interpretarse como un
evento de puerta. El monitor ya publica `status`, `/ready` y DTO de snapshot;
cualquier señal nueva debe preservar esos contratos.

## Decisión

- Crear el slice vertical `features/camera_health` con `domain/`,
  `application/` y sin infraestructura que importe otros slices.
- Muestrear el frame fuera del camino crítico: reutilizar el `job.frame` del
  `render_job`, o un `QualityThread` con buffer de capacidad 1 cuando
  `VISION_CORE_RENDER_ENABLED=0`.
- Clasificar `RESOLUTION_MISMATCH`, `ZONES_STALE`, `FROZEN_FRAME`,
  `BLURRY_FRAME` y `EXPOSURE_OUT_OF_RANGE`, con una precedencia estable para
  `reason` y conservando todas las señales activas en `signals`.
- Publicar `camera_quality` en `MonitorState.snapshot()` y en el DTO del
  snapshot, con `status: ok | degraded`; mantener `status` global, `/ready` y
  la generación de eventos intactos.
- Emitir gauge, contadores por transición y un log de advertencia; mostrar un
  aviso textual no intrusivo en el monitor sin bloquear la interfaz.
- Leer la configuración desde `core/config` con overrides por
  `VISION_CORE_CAMERA_QUALITY_<CAMERA_ID>_*`.

## Consecuencias

### Positivas

- La degradación es observable sin falsos positivos de acceso.
- El costo de visión por cuadro acotado por muestreo no compite con el render.
- El contrato HTTP sigue siendo versionable y compatible con clientes actuales.

### Negativas y costes

- Un nuevo slice, DTO anidado y hilo opcional amplían la superficie a mantener.
- Las señales son heurísticas: requieren revisión de umbrales con cámaras reales.

### Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| La inspección de calidad detiene el pipeline | Las excepciones se registran y se contabilizan en `vision_core_camera_quality_errors_total`. |
| Clientes que no esperan el campo nuevo | `camera_quality` siempre presente con defaults `ok`; golden DTO actualizado. |
| Avisos falsos por calibración pendiente | Sin zonas no se evalúa `ZONES_STALE`; `demo_zones` no cambia el estado global. |
| Saturación por logs o métricas | Gauge idempotente y contadores solo en transición a `degraded`. |

## Alternativas consideradas

1. Reutilizar `status: error` — descartado porque alteraría `/ready` y podría
   interpretarse como fallo del pipeline.
2. Emitir eventos de puerta — descartado porque mezcla calidad de imagen con
   analytics de acceso.
3. Analizar cada frame en el hilo principal — descartado por impacto en FPS.

## Verificación

```bash
python -m pytest -q tests/features/camera_health
python -m pytest -q tests/infrastructure/monitor tests/contracts tests/test_ui_security.py
python -m ruff check . && python -m ruff format --check .
python -m mypy
```

## Enmiendas

| Fecha | Cambio | Motivo | ADR que la motiva |
|---|---|---|---|
| - | - | - | - |
