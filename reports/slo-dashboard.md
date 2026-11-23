# Tablero de SLO — ECM-104

Generado: 2026-11-23T19:53:53Z · Ventana: snapshot · Fuente: smoke

| SLO | Actual | Umbral | Estado | Tendencia | Alerta | Runbook |
| --- | --- | --- | --- | --- | --- | --- |
| Disponibilidad instantánea del monitor | 100.00% | >= 99.00% | ok | estable | critical | [docs/runbooks/02-camara-caida-o-rtsp-inestable.md](../docs/runbooks/02-camara-caida-o-rtsp-inestable.md) |
| Frescura del frame | 0.80 seconds | <= 2.00 seconds | ok | estable | warning | [docs/runbooks/02-camara-caida-o-rtsp-inestable.md](../docs/runbooks/02-camara-caida-o-rtsp-inestable.md) |
| Latencia p95 de procesamiento | 60.00 ms | <= 60.00 ms | ok | estable | warning | [docs/runbooks/05-fps-bajo-o-latencia-alta.md](../docs/runbooks/05-fps-bajo-o-latencia-alta.md) |
| Entrega observada de eventos (proxy desde arranque) | 99.17% | >= 99.00% | ok | estable | warning | [docs/runbooks/06-no-se-generan-eventos.md](../docs/runbooks/06-no-se-generan-eventos.md) |
| Recuperación tras fallo de cámara | sin datos | <= 30.00 seconds | sin_datos | sin_datos_previos | critical | [docs/runbooks/02-camara-caida-o-rtsp-inestable.md](../docs/runbooks/02-camara-caida-o-rtsp-inestable.md) |

## Señales y códigos asociados

### Disponibilidad instantánea del monitor

- Señales: /ready.ready, vision_core_errors_total
- Códigos: VIDEO_SOURCE_UNAVAILABLE, CONFIGURATION_INVALID, INTERNAL_ERROR
- Alerta `alert_monitor_availability`: `critical`

### Frescura del frame

- Señales: /api/v1/state.age_seconds, vision_core_fps, vision_core_frames_discarded_total
- Códigos: VIDEO_FRAME_PENDING, VIDEO_FRAME_INVALID
- Alerta `alert_frame_freshness`: `warning`

### Latencia p95 de procesamiento

- Señales: /metrics.histograms.vision_core_frame_processing_duration_ms.p95, benchmarks/budgets.json
- Códigos: PIPELINE_FAILED
- Alerta `alert_processing_p95`: `warning`

### Entrega observada de eventos (proxy desde arranque)

- Señales: vision_core_events_emitted_total (base, desde arranque), /api/v1/state.persistence.failures (desde arranque)
- Códigos: PIPELINE_FAILED, VALIDATION_FAILED
- Alerta `alert_event_delivery`: `warning`

### Recuperación tras fallo de cámara

- Señales: vision_core_camera_recovery_seconds, vision_core_reconnections_total
- Códigos: VIDEO_SOURCE_UNAVAILABLE, VIDEO_FRAME_PENDING
- Alerta `alert_camera_recovery`: `critical`

> 1 SLO sin datos: el tablero no los cuenta como correctos.

