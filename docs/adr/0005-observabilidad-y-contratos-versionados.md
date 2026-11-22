# ADR 0005: Observabilidad, errores y contratos versionados

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-20 |
| Tipo | Operación / Contratos |
| Prioridad | Alta |
| Ticket | ECM-84 (documenta las decisiones de ECM-75, ECM-76 y ECM-31) |
| Etiquetas | `adr`, `observability`, `errors`, `api`, `logging` |
| Dependencias | ADR 0001; observabilidad estructurada y taxonomía de errores |
| Impacto | Diagnóstico de incidentes, API del monitor y clientes del evento |

## Contexto

Antes no había una forma consistente de responder "¿sigue vivo?", "¿está
listo?" ni "por qué falló". Los errores nativos mezclaban mensajes de
bibliotecas con datos potencialmente sensibles y el monitor publicaba rutas sin
versión, imposibilitando evolucionarlas sin romper clientes. Los runbooks
necesitan señales estables y comparables entre reinicios.

## Decisión

- Publicar `/health` (liveness), `/ready` (configuración, modelo, video y
  disco; `503` si falla) y `/metrics` (JSON con contadores, gauges e
  histogramas). La API operativa es `/api/v1/state` y `/api/v1/frame?after=N`;
  `/api/state` y `/api/frame` quedan como alias deprecados con cabecera
  `Deprecation`.
- Estructurar los logs en JSON cuando `VISION_CORE_LOG_JSON=1`: `timestamp`,
  `level`, `service`, `camera_id`, `event_id`, `person_id`, `duration_ms`,
  `error_code` y `message`. Las URLs con credenciales se redactan; no se
  registran frames, crops, embeddings ni rutas sensibles.
- Usar la jerarquía `VisionCoreError` en `src/vision_core/core/errors/`.
  Cada error expone `code` estable, `message` seguro, `retryable` y `context`
  filtrado. El borde HTTP publica solo `{"error":{"code","message","request_id"}}`.
- El envelope y el esquema de eventos están versionados (`v1`,
  `schema_version=1.0.0`). Un cambio incompatible exige un prefijo nuevo; no
  se modifican las formas publicadas.
- Las métricas no usan `person_id`, rutas ni URLs como labels. Los histogramas
  guardan una ventana de 1000 muestras para `min`/`max` y acumulan `count`,
  `sum` y `avg` desde el arranque.

## Consecuencias

### Positivas

- Los runbooks parten de señales concretas (`/ready`, `error_code`,
  `vision_core_events_emitted_total`) en vez de corazonadas.
- Un cliente puede detectar la deprecación de `/api/*` y migrar a `/api/v1/*`.
- Los mensajes de error son seguros para pegar en un ticket.

### Negativas y costes

- `/metrics` es JSON, no formato Prometheus nativo; no se añade dependencia.
- Mantener alias deprecados y códigos estables limita renombrar libremente.

### Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Un cambio de formato rompa al monitor | Contratos en `docs/api-contracts.md` y pruebas de compatibilidad DTO. |
| Fuga de credenciales o PII en logs | Redacción en settings y filtrado de `context` en la taxonomía. |
| Métricas engañosas por comparar ventanas distintas | Documentar la ventana de histogramas y usar p50/p95 del profiling para FPS. |

## Alternativas consideradas

1. **Logs de texto libre + `print`.** Descartada: no consultables y con datos
   sensibles.
2. **Exposición Prometheus nativa.** Descartada por ahora: `/metrics` JSON ya
   cubre el diagnóstico sin nueva dependencia.
3. **Errores HTTP genéricos sin códigos.** Descartada: imposibilita runbooks
   repetibles y clientes que distingan `retryable`.

## Verificación

```bash
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/ready
curl http://127.0.0.1:8080/metrics
curl http://127.0.0.1:8080/api/v1/state
python -m pytest -q
```

Detalle operativo en [observabilidad](../observability.md),
[catálogo de errores](../errors.md) y
[contratos versionados](../api-contracts.md).

## Enmiendas

| Fecha | Cambio | Motivo | ADR que la motiva |
|---|---|---|---|
| - | - | - | - |
