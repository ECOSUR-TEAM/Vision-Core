# ADR 0010: Sinks de eventos con entrega idempotente y backpressure

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-23 |
| Tipo | Arquitectura |
| Prioridad | Media |
| Ticket | ECM-102 |
| Etiquetas | `adr`, `events`, `webhook`, `mqtt`, `idempotency`, `backpressure` |
| Dependencias | ADR 0002 (persistencia), ADR 0003 (backpressure), ADR 0005 (observabilidad), tickets 31/34/35/37 |
| Impacto | Nuevo puerto de salida `EventSink`, slice `features/events`, cola acotada y entrega webhook opcional |

## Contexto

Hoy los eventos solo se imprimen por stdout o se consumen desde el monitor. No
existe un mecanismo de entrega con semántica explícita, reintentos ni control
del impacto colateral cuando el destino falla. El pipeline invoca un
`EventConsumer` de forma sincrónica en `RunPipeline._process_frame`; cualquier
llamada de red ahí bloquearía la captura.

La taxonomía de errores (ticket 31 / ADR 0005) ya define `code`, `message`,
`retryable` y `context` saneado; la persistencia (ADR 0002) ya define
`UNIQUE(event_id)` y una clave derivada del payload; el modelo de ejecución
(ADR 0003) exige colas acotadas con descarte de lo viejo y sin bloqueo del
productor.

## Decisión

1. Crear el slice `features/events` con el puerto `EventSink` en
   `domain/ports/event_sink.py` y el sobre serializable `EventEnvelope` en
   `core/dto/event_envelope.py`. `RunPipeline` recibe un `EventSink | None`
   opcional y solo llama a `send`; no importa adaptadores.
2. `EventSinkDispatcher` (`application/use_cases/dispatch_events.py`) implementa
   el puerto: cola acotada con `put_nowait`, política `drop-oldest` por defecto,
   dedupe LRU por clave, reintentos con backoff exponencial + jitter, límite de
   intentos y dead-letter en memoria. Un hilo daemon hace la entrega; el pipeline
   nunca espera red.
3. La clave de idempotencia se calcula con `idempotency_key_for()`: `event_id`
   explícito o SHA-256 del payload canónico del ticket 31. Se reutiliza la misma
   función en persistencia, sin crear una segunda definición.
4. `WebhookEventSink` envía el payload sin alterar el contrato de eventos,
   `Idempotency-Key` con la clave, timeout, verificación TLS por defecto y
   headers configurables. Los errores usan `PipelineError` (5xx/red,
   `retryable=True`) y `ValidationError` (4xx, `retryable=False`), sin códigos
   nuevos. URL y headers nunca entran en logs ni en `context`.
5. MQTT queda detrás de `VISION_CORE_EVENT_SINK_BACKEND=mqtt`. No se añade
   `paho-mqtt`: el adaptador falla con `CONFIGURATION_INVALID` y el puerto queda
   documentado para una futura adopción.
6. No se crea una tabla de outbox. Se reutiliza la identidad estable de ADR
   0002; el resto del estado de entrega es en memoria y su pérdida en reinicio
   se documenta en `docs/event-sinks.md`.

## Consecuencias

### Positivas

- El pipeline no importa implementaciones concretas y sigue sin bloquearse.
- At-least-once con clave estable permite deduplicar en el consumidor.
- Reintentos limitados, dead-letter y contadores explícitos hacen auditable la
  entrega; no hay bucles infinitos ni colas sin límite.
- Sin dependencias nuevas: solo `stdlib` y la taxonomía existente.

### Negativas y costes

- Un evento puede entregarse dos veces si el consumidor no respeta la clave.
- La ventana de dedupe y el dead-letter son en memoria: se pierden al reiniciar.
- `drop-oldest` sacrifica eventos antes que frames, en línea con ADR 0003.

### Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Filtrar secretos en logs o errores | URL/headers con `repr=False`; mensajes sin valores; `sanitize_context()`; tests con `caplog`. |
| Cola llena por destino lento | `put_nowait` + `dropped_total`/`queue_depth`; `close()` con plazo de 2 s. |
| Reintento infinito | `max_attempts` y backoff tope con jitter. |
| Cambio accidental del formato de evento | El sobre serializa el DTO del ticket 31; snapshot de DTO actualizado explícitamente. |

## Alternativas consideradas

1. Llamada HTTP sincrónica desde `RunPipeline` — descartada: bloquea el pipeline
   y propaga fallos del destino a la captura.
2. Broker (Kafka/RabbitMQ/Redis Streams) — descartado mientras haya un solo nodo
   (ADR 0003); añadiría servicio y dependencias sin necesidad actual.
3. Outbox SQLite nuevo — descartado por ahora: ADR 0002 ya da claves estables y
   el alcance no autoriza persistencia nueva; se documenta la pérdida en reinicio.
4. `paho-mqtt` incluido por defecto — descartado: sin consumidor real solo
   añade superficie de supply chain; queda como puerto documentado.

## Verificación

```bash
python -m pytest tests/features/events tests/infrastructure/events -q
python -m pytest -q
ruff check . && ruff format --check .
python -m mypy
```

La suite cubre éxito, timeout, 5xx con reintento, 4xx permanente, duplicado con
la misma clave, dead-letter, secretos ausentes en logs y cola llena sin bloquear
el pipeline.

## Enmiendas

| Fecha | Cambio | Motivo | ADR que la motiva |
|---|---|---|---|
| 2026-11-23 | Best-effort explícito: la clave se marca tras 2xx, drop/DLQ/apagado liberan el id para reenvío; `close()` señala cierre, interrumpe reintentos y cierra el destino tras el worker; jitter antes del tope; 408/429 retryables. | Revisión de PR: la semántica documentada no coincidía con pérdidas, dedupe y shutdown. | ADR 0002, ADR 0003, ADR 0005 |
| 2026-11-23 | Webhook sin redirecciones, hosts no públicos rechazados salvo opt-in, DNS validado antes de cada envío, timeout `<= 30 s` y warning al desactivar TLS. | Revisión de PR: posible filtrado de headers hacia otro host y configuración insegura. | ADR 0004, ADR 0008 |
