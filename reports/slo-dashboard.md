# Tablero de SLO — ECM-104

Generado: 2026-11-23T18:56:52Z · Ventana: 24h

| SLO | Actual | Umbral | Estado | Tendencia | Alerta | Runbook |
| --- | --- | --- | --- | --- | --- | --- |
| Disponibilidad del monitor | 100.00% | >= 99.00% | ok | estable | critical | [docs/runbooks/02-camara-caida-o-rtsp-inestable.md](../docs/runbooks/02-camara-caida-o-rtsp-inestable.md) |
| Frescura del frame | 0.80 seconds | <= 2.00 seconds | ok | estable | warning | [docs/runbooks/02-camara-caida-o-rtsp-inestable.md](../docs/runbooks/02-camara-caida-o-rtsp-inestable.md) |
| Latencia p95 de procesamiento | 60.00 ms | <= 60.00 ms | ok | estable | warning | [docs/runbooks/05-fps-bajo-o-latencia-alta.md](../docs/runbooks/05-fps-bajo-o-latencia-alta.md) |
| Tasa de entrega de eventos | 99.17% | >= 99.00% | ok | estable | warning | [docs/runbooks/06-no-se-generan-eventos.md](../docs/runbooks/06-no-se-generan-eventos.md) |
| Recuperación tras fallo de cámara | 12.00 seconds | <= 30.00 seconds | ok | estable | critical | [docs/runbooks/02-camara-caida-o-rtsp-inestable.md](../docs/runbooks/02-camara-caida-o-rtsp-inestable.md) |

## Señales y códigos asociados

### Disponibilidad del monitor

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

### Tasa de entrega de eventos

- Señales: vision_core_events_emitted_total, /api/v1/state.persistence.failures
- Códigos: PIPELINE_FAILED, VALIDATION_FAILED
- Alerta `alert_event_delivery`: `warning`

### Recuperación tras fallo de cámara

- Señales: vision_core_reconnections_total, incident-drills.recovery_seconds
- Códigos: VIDEO_SOURCE_UNAVAILABLE, VIDEO_FRAME_PENDING
- Alerta `alert_camera_recovery`: `critical`

