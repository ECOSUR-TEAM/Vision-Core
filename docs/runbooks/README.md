# Runbooks

Procedimientos cortos y verificables para incidentes y tareas operativas. Cada
runbook tiene el mismo formato: **síntoma → verificación → acción → señal de
éxito → escalado**. Usa el que corresponda y vuelve a llenar el registro al
final.

| Runbook | Cuándo usarlo |
|---|---|
| [01. Arranque y parada](01-arranque-y-parada.md) | Iniciar, reiniciar o detener el stack; verificar que arrancó |
| [02. Cámara caída o RTSP inestable](02-camara-caida-o-rtsp-inestable.md) | `/ready` marca `video_source=false`, reconexiones o stream vacío |
| [03. Modelo no encontrado o error de inferencia](03-modelo-no-encontrado-o-error-de-inferencia.md) | `/ready` marca `model=false` o aparece `MODEL_*` / `REID_*` |
| [04. Disco lleno y retención](04-disco-lleno-y-retencion.md) | Readiness de disco, SQLite creciendo o `failures > 0` |
| [05. FPS bajo o latencia alta](05-fps-bajo-o-latencia-alta.md) | Monitor lento, frames descartados o p95 alto |
| [06. No se generan eventos](06-no-se-generan-eventos.md) | Hay video y detecciones, pero `vision_core_events_emitted_total` no crece |
| [07. Rollback de versión](07-rollback-de-version.md) | Una versión nueva degrada el servicio y hay que volver atrás |
| [08. Alerta de SLO](08-alerta-de-slo.md) | Una alerta de `config/slo.json` supera su umbral |

## Antes de empezar

1. Identifica el entorno: stack por defecto (sintético), perfil `camera` o
   Python local. Los comandos cambian entre ellos.
2. Anota hora, commit o versión y qué cambió justo antes del síntoma.
3. Consulta siempre las señales antes de reiniciar: `/health`, `/ready`,
   `/metrics` y los logs. Reiniciar sin evidencia borra pistas del estado en
   memoria.
4. No pegues URLs RTSP con credenciales, logs completos ni imágenes de personas
   en tickets. Usa `error_code` y contadores.

```bash
docker compose ps -a
docker compose --profile camera logs --tail 80 vision-core
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/ready
curl http://127.0.0.1:8080/metrics
```

Fondo: [observabilidad](../observability.md), [catálogo de errores](../errors.md),
[operaciones](../operations.md) y [ADR 0005](../adr/0005-observabilidad-y-contratos-versionados.md).

## Registro de ejecución

| Campo | Valor |
|---|---|
| Runbook ejecutado |  |
| Fecha y hora |  |
| Versión / commit |  |
| Señales observadas |  |
| Acción aplicada |  |
| Señal de éxito comprobada |  |
| Revisor |  |
