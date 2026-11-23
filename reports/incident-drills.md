# Resultados de simulacros — ECM-104

Generado: 2026-11-23T18:56:43Z

| Simulacro | SLO | Detección | Recuperación | Resultado | Runbook |
| --- | --- | --- | --- | --- | --- |
| RTSP desconectado | camera_recovery | 1.00s / 1.00s | 12.00s / 12.00s | passed | [docs/runbooks/02-camara-caida-o-rtsp-inestable.md](../docs/runbooks/02-camara-caida-o-rtsp-inestable.md) |
| Frame congelado | frame_freshness | 0.50s / 0.50s | 1.50s / 1.50s | passed | [docs/runbooks/02-camara-caida-o-rtsp-inestable.md](../docs/runbooks/02-camara-caida-o-rtsp-inestable.md) |
| Pesos de modelo ausentes o corruptos | monitor_availability | 0.50s / 0.50s | 4.00s / 4.00s | passed | [docs/runbooks/03-modelo-no-encontrado-o-error-de-inferencia.md](../docs/runbooks/03-modelo-no-encontrado-o-error-de-inferencia.md) |
| Sink de eventos caído | event_delivery | 2.00s / 2.00s | 18.00s / 18.00s | passed | [docs/runbooks/06-no-se-generan-eventos.md](../docs/runbooks/06-no-se-generan-eventos.md) |
| Disco lleno | monitor_availability | 1.00s / 1.00s | 9.00s / 9.00s | passed | [docs/runbooks/04-disco-lleno-y-retencion.md](../docs/runbooks/04-disco-lleno-y-retencion.md) |
| Reinicio del contenedor | monitor_availability | 0.50s / 0.50s | 15.00s / 15.00s | passed | [docs/runbooks/01-arranque-y-parada.md](../docs/runbooks/01-arranque-y-parada.md) |

## Evidencia

### RTSP desconectado

- RTSP desconectado: detectado en 1.00s y recuperado en 12.00s; El monitor marca stale y /ready cae; la reconexión restaura /ready sin reiniciar el proceso.
- Señales: vision_core_reconnections_total, vision_core_errors_total
- Códigos: VIDEO_SOURCE_UNAVAILABLE, VIDEO_FRAME_PENDING

### Frame congelado

- Frame congelado: detectado en 0.50s y recuperado en 1.50s; La calidad degrada sin cortar el video; el aviso es textual y no bloquea el conteo.
- Señales: vision_core_camera_quality_degraded_total, /api/v1/state.age_seconds
- Códigos: VIDEO_FRAME_INVALID

### Pesos de modelo ausentes o corruptos

- Pesos de modelo ausentes o corruptos: detectado en 0.50s y recuperado en 4.00s; /ready pasa a 503 antes de abrir stream; el arranque falla temprano con código estable.
- Señales: /ready.checks.model, vision_core_errors_total
- Códigos: MODEL_UNAVAILABLE, CONFIGURATION_INVALID

### Sink de eventos caído

- Sink de eventos caído: detectado en 2.00s y recuperado en 18.00s; La persistencia falla en modo fail-open; el pipeline sigue y contabiliza fallos.
- Señales: vision_core_events_emitted_total, /api/v1/state.persistence.failures
- Códigos: PIPELINE_FAILED, VALIDATION_FAILED

### Disco lleno

- Disco lleno: detectado en 1.00s y recuperado en 9.00s; /ready marca disk=false y la retención deja de escribir sin tumbar el monitor.
- Señales: /ready.checks.disk, /api/v1/state.persistence.failures
- Códigos: CONFIGURATION_INVALID

### Reinicio del contenedor

- Reinicio del contenedor: detectado en 0.50s y recuperado en 15.00s; El contenedor vuelve a /health alive; los IDs de sesión y el historial volátil se reinician.
- Señales: /health.status, /metrics.uptime_seconds
- Códigos: VIDEO_SOURCE_UNAVAILABLE

