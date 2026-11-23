# Runbook 08: Alerta de SLO

**Síntoma:** una alerta de `config/slo.json` pasa su umbral: disponibilidad,
frescura del frame, p95 de procesamiento, entrega de eventos o recuperación de
cámara.

## Verificación rápida

```bash
make slo-check
make slo-dashboard
cat reports/slo-dashboard.md
```

Comprueba en el tablero el valor actual, el umbral, la tendencia, la severidad
y el runbook enlazado. Confirma la señal directa en `/ready`, `/metrics` o
`/api/v1/state` según el mapeo de [slo.md](../slo.md).

## Acción

| Alerta | Severidad | Primer runbook |
|---|---|---|
| `alert_monitor_availability` | `critical` | [02. Cámara caída o RTSP inestable](02-camara-caida-o-rtsp-inestable.md) |
| `alert_frame_freshness` | `warning` | [02. Cámara caída o RTSP inestable](02-camara-caida-o-rtsp-inestable.md) |
| `alert_processing_p95` | `warning` | [05. FPS bajo o latencia alta](05-fps-bajo-o-latencia-alta.md) |
| `alert_event_delivery` | `warning` | [06. No se generan eventos](06-no-se-generan-eventos.md) |
| `alert_camera_recovery` | `critical` | [02. Cámara caída o RTSP inestable](02-camara-caida-o-rtsp-inestable.md) |

No cambies umbrales durante el incidente. Si la alerta es `critical` y `/ready`
sigue en `503` tras la acción correctiva, aplica
[07. Rollback de versión](07-rollback-de-version.md).

## Señal de éxito

- El SLO vuelve a `ok` en [el tablero](../../reports/slo-dashboard.md).
- El `error_code` asociado deja de aparecer en logs JSON.
- La tendencia deja de ser `empeorando` en la siguiente lectura.

## Escalado

Registra hora, SLO, valor, umbral, tendencia y runbook ejecutado en el
[registro de ejecución](README.md#registro-de-ejecución). Escala al responsable
del área según el runbook destino. No hay pager real ni on-call en este alcance;
la notificación se hace por el canal definido en el release del ticket 37.
