# SLOs, alertas y tablero operativo

ECM-104 define cinco SLOs para el monitor de una cámara. Los umbrales son los
acordados para este ticket y se revisan con los presupuestos de
[rendimiento](performance.md). Sin un recolector externo no hay agregación de
24 h: la ventana de esta entrega es `snapshot` (disponibilidad, frescura y p95)
o `desde arranque` (proxy de entrega de eventos). La recuperación de cámara
requiere el gauge opcional `vision_core_camera_recovery_seconds`; mientras no
exista, el tablero la marca `sin_datos` y no la cuenta como correcta.

| SLO | Objetivo | Señal principal | Códigos asociados | Alerta / runbook |
| --- | --- | --- | --- | --- |
| Disponibilidad instantánea del monitor | ≥ 99 % por snapshot | `/ready.ready` | `VIDEO_SOURCE_UNAVAILABLE`, `CONFIGURATION_INVALID`, `INTERNAL_ERROR` | `critical` · [RTSP inestable](runbooks/02-camara-caida-o-rtsp-inestable.md) |
| Frescura del frame | ≤ 2 s | `/api/v1/state.age_seconds` | `VIDEO_FRAME_PENDING`, `VIDEO_FRAME_INVALID` | `warning` · [RTSP inestable](runbooks/02-camara-caida-o-rtsp-inestable.md) |
| Latencia p95 de procesamiento | ≤ 60 ms | `/metrics.histograms.vision_core_frame_processing_duration_ms.p95` | `PIPELINE_FAILED` | `warning` · [FPS bajo o latencia alta](runbooks/05-fps-bajo-o-latencia-alta.md) |
| Entrega observada de eventos (proxy desde arranque) | ≥ 99 % desde arranque | `vision_core_events_emitted_total` (clave base) y `persistence.failures` | `PIPELINE_FAILED`, `VALIDATION_FAILED` | `warning` · [Sin eventos](runbooks/06-no-se-generan-eventos.md) |
| Recuperación tras fallo de cámara | ≤ 30 s | `vision_core_camera_recovery_seconds` (gauge opcional) | `VIDEO_SOURCE_UNAVAILABLE`, `VIDEO_FRAME_PENDING` | `critical` · [RTSP inestable](runbooks/02-camara-caida-o-rtsp-inestable.md) |

La configuración ejecutable está en [`config/slo.json`](../config/slo.json).
Cada SLO tiene una única alerta con `id`, `severity` y `runbook`. El check
`check_slo_config` rechaza SLOs duplicados, umbrales inválidos, códigos fuera
del [catálogo](errors.md), runbooks inexistentes, simulacros huérfanos y un
objetivo de p95 por encima del presupuesto `synthetic-cpu-320x240` de
`benchmarks/budgets.json`. Si se le pasa `--metrics-json`, también rechaza un
p95 observado por encima de ese presupuesto.

## Comandos

```bash
make slo-check       # valida SLOs, alertas y simulacros
make incident-drills # ejecuta los seis simulacros y escribe reports/
make slo-dashboard   # ejecuta simulacros y genera el tablero
```

```bash
PYTHONPATH=src python -m vision_core.scripts.check_slo_config \
  --metrics-json reports/metrics-snapshot.json
```

También se puede alimentar el tablero con una captura real de `/metrics`,
`/ready` y `/api/v1/state`:

```bash
PYTHONPATH=src python -m vision_core.scripts.generate_slo_dashboard \
  --snapshot-json reports/slo-live-snapshot.json
```

El JSON de entrada debe tener las claves `metrics`, `health` y `state` con los
payloads de esos endpoints, recortados a lo necesario: no incluyas `people`,
`events`, `person_id`, URLs RTSP ni rutas del filesystem. Esos archivos crudos
no se versionan. Sin `--snapshot-json`, el comando usa una captura determinista
de smoke generada con los instrumentos reales del proyecto y marca la fuente
como `smoke`.

## Tablero y artefactos

- [`reports/slo-dashboard.md`](../reports/slo-dashboard.md): estado actual,
  tendencia, umbral, severidad y runbook por SLO; distingue `sin_datos`.
- [`reports/slo-dashboard.json`](../reports/slo-dashboard.json): salida
  estructurada para consumir desde otro sistema.
- [`reports/incident-drills.md`](../reports/incident-drills.md): latencias
  inyectadas por simulacro; no son mediciones de producción.
- [`reports/incident-drills.json`](../reports/incident-drills.json): plan de
  simulacros con objectives, señales y códigos ejercitados.
- [`reports/slo-history.json`](../reports/slo-history.json): última lectura por
  SLO para calcular la tendencia de la siguiente generación.

Los archivos `reports/` se generan y se versionan con el PR; no contienen datos
de personas. La agregación de 24 h requiere un recolector externo.

## Simulacros

| ID | Latencia inyectada | Resultado esperado del exercise |
| --- | --- | --- |
| `rtsp_disconnected` | 1 s detección / 12 s recuperación | `/ready` cae, `stale` y reconexión sin reiniciar |
| `frozen_frame` | 0.5 s detección / 1.5 s recuperación | Calidad degradada con reason `FROZEN_FRAME`, aviso textual y conteo continúa |
| `weights_missing` | 0.5 s detección / 4 s recuperación | `/ready` = 503 antes de abrir stream |
| `event_sink_down` | 2 s detección / 18 s recuperación | `fail-open`, fallos contabilizados |
| `disk_full` | 1 s detección / 9 s recuperación | `disk=false`, retención detenida, monitor vivo |
| `container_restart` | 0.5 s detección / 15 s recuperación | `/health alive`, estado volátil reiniciado |

Los simulacros son ejercicios controlados y repetibles: inyectan latencias en
el artefacto, no fallos reales sobre producción, y no prueban pagers. Cada fila
enlaza a su runbook y compara la latencia inyectada con su objetivo. Si una
latencia inyectada supera el objetivo, el comando termina con código de salida
1 y el tablero conserva el registro de la desviación.
