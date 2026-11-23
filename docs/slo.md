# SLOs, alertas y tablero operativo

ECM-104 define cinco SLOs para el monitor de una cámara. Los umbrales son los
acordados para este ticket y se revisan con los presupuestos de
[rendimiento](performance.md) y los datos de campo del ticket 37.

| SLO | Objetivo | Señal principal | Códigos asociados | Alerta / runbook |
| --- | --- | --- | --- | --- |
| Disponibilidad del monitor | ≥ 99 % en 24 h | `/ready.ready` + `vision_core_errors_total` | `VIDEO_SOURCE_UNAVAILABLE`, `CONFIGURATION_INVALID`, `INTERNAL_ERROR` | `critical` · [RTSP inestable](runbooks/02-camara-caida-o-rtsp-inestable.md) |
| Frescura del frame | ≤ 2 s | `/api/v1/state.age_seconds` + `vision_core_fps` | `VIDEO_FRAME_PENDING`, `VIDEO_FRAME_INVALID` | `warning` · [RTSP inestable](runbooks/02-camara-caida-o-rtsp-inestable.md) |
| Latencia p95 de procesamiento | ≤ 60 ms | `/metrics.histograms.vision_core_frame_processing_duration_ms.p95` | `PIPELINE_FAILED` | `warning` · [FPS bajo o latencia alta](runbooks/05-fps-bajo-o-latencia-alta.md) |
| Entrega de eventos | ≥ 99 % en 24 h | `vision_core_events_emitted_total` + `persistence.failures` | `PIPELINE_FAILED`, `VALIDATION_FAILED` | `warning` · [Sin eventos](runbooks/06-no-se-generan-eventos.md) |
| Recuperación tras fallo de cámara | ≤ 30 s | `vision_core_reconnections_total` + resultados de simulacro | `VIDEO_SOURCE_UNAVAILABLE`, `VIDEO_FRAME_PENDING` | `critical` · [RTSP inestable](runbooks/02-camara-caida-o-rtsp-inestable.md) |

La configuración ejecutable está en [`config/slo.json`](../config/slo.json).
Cada SLO tiene una única alerta con `id`, `severity` y `runbook`. El check
`check_slo_config` rechaza SLOs duplicados, umbrales inválidos, códigos fuera
del [catálogo](errors.md), runbooks inexistentes, simulacros huérfanos y p95 por
encima del presupuesto `synthetic-cpu-320x240` de `benchmarks/budgets.json`.

## Comandos

```bash
make slo-check       # valida SLOs, alertas y simulacros
make incident-drills # ejecuta los seis simulacros y escribe reports/
make slo-dashboard   # ejecuta simulacros y genera el tablero
```

También se puede alimentar el tablero con una captura real de `/metrics`,
`/ready` y `/api/v1/state`:

```bash
PYTHONPATH=src python -m vision_core.scripts.generate_slo_dashboard \
  --snapshot-json reports/slo-snapshot.json
```

El JSON de entrada debe tener las claves `metrics`, `health` y `state` con los
payloads devueltos por esos endpoints. Sin `--snapshot-json`, el comando usa una
captura determinista de smoke generada con los instrumentos reales del proyecto.

## Tablero y artefactos

- [`reports/slo-dashboard.md`](../reports/slo-dashboard.md): estado actual,
  tendencia, umbral, severidad y runbook por SLO.
- [`reports/slo-dashboard.json`](../reports/slo-dashboard.json): salida
  estructurada para consumir desde otro sistema.
- [`reports/incident-drills.md`](../reports/incident-drills.md): detección y
  recuperación observadas por simulacro.
- [`reports/incident-drills.json`](../reports/incident-drills.json): evidencia
  estructurada para el artefacto de release del ticket 37.
- [`reports/slo-history.json`](../reports/slo-history.json): última lectura por
  SLO para calcular la tendencia de la siguiente generación.

Los archivos `reports/` se generan y se versionan con el PR; adjúntalos también
al artefacto de release. La agregación de 24 h requiere un recolector externo:
este tablero muestra el valor puntual disponible en el proceso y la tendencia
respecto de la lectura anterior.

## Simulacros

| ID | Fallo inyectado | Resultado esperado |
| --- | --- | --- |
| `rtsp_disconnected` | Fuente RTSP desconectada | `/ready` cae, `stale` y reconexión sin reiniciar |
| `frozen_frame` | Frame congelado | Calidad degradada, aviso textual, conteo continúa |
| `weights_missing` | Pesos ausentes o corruptos | `/ready` = 503 antes de abrir stream |
| `event_sink_down` | Persistencia de eventos caída | `fail-open`, fallos contabilizados |
| `disk_full` | Espacio insuficiente | `disk=false`, retención detenida, monitor vivo |
| `container_restart` | Reinicio del contenedor | `/health alive`, estado volátil reiniciado |

Los simulacros son controlados y repetibles: no ejecutan fallos reales sobre
producción ni prueban pagers. Cada fila enlaza a su runbook y registra tiempos
de detección y recuperación. Si un simulacro supera su objetivo, el comando
termina con código de salida 1 y el tablero marca la brecha.
