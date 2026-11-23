# Sinks de eventos: entrega, idempotencia y backpressure (ECM-102)

Los eventos del pipeline pueden entregarse a sistemas externos sin bloquear la
captura. El pipeline solo conoce el puerto `EventSink`
(`src/vision_core/features/events/domain/ports/event_sink.py`); los adaptadores
concretos viven en `features/events/infrastructure/adapters`.

## Contrato

- `EventSink.send(EventEnvelope)` encola un sobre y devuelve de inmediato.
- `EventSink.close()` drena el trabajo pendiente con un plazo de 2 s y cierra el
  destino; se llama desde el `finally` del pipeline.
- `EventEnvelope` (`core/dto/event_envelope.py`) tiene `event_id` (clave de
  idempotencia) y `payload` (el JSON del ticket 31: `event`, `person_id`,
  `timestamp`, `metadata`, `schema_version`). El formato del evento **no cambia**:
  `event_id` viaja fuera del payload y, en webhook, como header
  `Idempotency-Key`.
- La clave se deriva con `idempotency_key_for()`: usa `event_id` explícito o un
  SHA-256 determinista del payload serializado. Es estable entre reinicios, la
  misma regla que `UNIQUE(event_id)` de ADR 0002.

## Semántica de entrega

| Aspecto | Comportamiento |
|---|---|
| Semántica | **At-least-once**. El consumidor debe deduplicar por `Idempotency-Key`. |
| Dedupe local | Ventana LRU de `dedupe_size` claves; un `event_id` repetido se contabiliza y no se encola. |
| Reintentos | Máximo `max_attempts` intentos; backoff exponencial `base * 2^(intento-1)` limitado por `retry_max_seconds`, con jitter uniforme `[1-j, 1+j]`. |
| Errores reintentables | `PipelineError` con `retryable=True` (5xx, timeout, red). Se reutiliza el catálogo de ADR/errors; no hay códigos nuevos. |
| Errores permanentes | `ValidationError` con `retryable=False` (4xx): van directo a dead-letter. |
| Dead-letter | Cola en memoria de `dead_letter_size` entradas `(EventEnvelope, code)`, consultable en tests y diagnóstico. No se registran payloads. |
| Cola | Acotada (`queue_size`). `send` usa `put_nowait`; con `drop-oldest` (default, ADR 0003) descarta el evento más viejo; con `drop-newest` descarta el entrante. Nunca bloquea el pipeline. |
| Apagado | `close()` detiene el worker y espera hasta 2 s; lo que no se entregó se cuenta como descartado. |

La entrega se ejecuta en un hilo daemon distinto del pipeline. Un fallo del
destino, del callback de dead-letter o del encolado se aisla y se contabiliza;
`RunPipeline._process_frame` sigue produciendo eventos para el monitor y la
persistencia.

## Persistencia

El store de ADR 0002 se reutiliza **solo** para la identidad estable del
evento (`event_id` / `event_id_for`). No hay tabla de outbox nueva: el estado de
entrega, la ventana de dedupe, los reintentos pendientes y el dead-letter son
**en memoria**. Tras un reinicio, un evento cuyo envío no se completó puede
reintentarse desde el productor si este vuelve a emitirlo; la clave derivada del
payload evita contarlo dos veces en el consumidor. Si se necesita durabilidad de
la entrega, el siguiente paso es una tabla `event_outbox` con `UNIQUE(event_id)`
y un worker que la drene (fuera del alcance de ECM-102).

## Configuración

Las variables se validan en `core/config/event_sink_settings.py` y se agrupan en
`Settings.events`. Errores de configuración usan `SettingsError`.

| Variable | Default | Descripción |
|---|---|---|
| `VISION_CORE_EVENT_SINK_BACKEND` | `none` | `none`, `webhook` o `mqtt`. |
| `VISION_CORE_EVENT_SINK_WEBHOOK_URL` | — | URL `http(s)://` del destino. Obligatoria para `webhook`. Sin credenciales incrustadas. |
| `VISION_CORE_EVENT_SINK_HEADERS` | `{}` | JSON objeto `{"Nombre": "valor"}`; sobrescribe headers por defecto. |
| `VISION_CORE_EVENT_SINK_TLS_VERIFY` | `1` | Verificación TLS del certificado. Desactivar solo en entornos controlados. |
| `VISION_CORE_EVENT_SINK_TIMEOUT_SECONDS` | `2.0` | Timeout por petición. |
| `VISION_CORE_EVENT_SINK_QUEUE_SIZE` | `256` | Capacidad de la cola acotada. |
| `VISION_CORE_EVENT_SINK_OVERFLOW_POLICY` | `drop-oldest` | `drop-oldest` o `drop-newest`. |
| `VISION_CORE_EVENT_SINK_MAX_ATTEMPTS` | `3` | Intentos totales por evento (incluye el primero). |
| `VISION_CORE_EVENT_SINK_RETRY_BASE_SECONDS` | `0.2` | Backoff base. |
| `VISION_CORE_EVENT_SINK_RETRY_MAX_SECONDS` | `5.0` | Tope del backoff. |
| `VISION_CORE_EVENT_SINK_RETRY_JITTER` | `0.2` | Jitter relativo `[0, 1]`. |
| `VISION_CORE_EVENT_SINK_DEDUPE_SIZE` | `4096` | Tamaño de la ventana LRU de idempotencia. |
| `VISION_CORE_EVENT_SINK_DEAD_LETTER_SIZE` | `128` | Entradas conservadas en el dead-letter. |
| `VISION_CORE_EVENT_SINK_MQTT_HOST` / `_PORT` / `_TOPIC` / `_QOS` | — / `1883` / — / `0` | Solo `backend=mqtt`; hoy falla en arranque (ver abajo). |

Ejemplo mínimo:

```bash
VISION_CORE_EVENT_SINK_BACKEND=webhook
VISION_CORE_EVENT_SINK_WEBHOOK_URL=http://127.0.0.1:9000/events
VISION_CORE_EVENT_SINK_HEADERS='{"Authorization": "Bearer ..."}'
VISION_CORE_EVENT_SINK_QUEUE_SIZE=128
```

## Secretos

- La URL y los valores de headers se guardan con `repr=False` y **nunca** se
  incluyen en mensajes de error, contexto ni logs: los errores informan solo
  `status`, `transport`, `code` y número de intentos.
- Se rechazan URLs con `user:password@`; los mensajes de validación nombran la
  variable, nunca su valor.
- Los mensajes pasan por la taxonomía `VisionCoreError` → `sanitize_context()`,
  que descarta claves como `authorization`, `token`, `url` o `password`.
- Para rotar credenciales, inyecta el secreto por entorno en
  `VISION_CORE_EVENT_SINK_HEADERS`; no lo escribas en `.env` versionado.

## Observabilidad

Métricas en `/metrics` (prefijo `vision_core_event_sink_`):

| Métrica | Significado |
|---|---|
| `submitted_total` | Llamadas a `send`, incluidos duplicados y descartes. |
| `delivered_total` | Entregas confirmadas (2xx). |
| `retried_total` | Reintentos realizados. |
| `dropped_total` | Eventos descartados por cola llena. |
| `duplicate_total` | Claves suprimidas por idempotencia. |
| `dead_letter_total` | Eventos agotados o permanentes. |
| `queue_depth` | Profundidad actual de la cola (gauge). |

Los logs estructurados siguen el contrato de ADR 0005: solo `code`, `attempts`,
`camera_id` y `event_id` cuando aplica; nunca payloads, URLs ni headers.

## MQTT

El puerto `EventSink` ya soporta un adaptador MQTT, pero **no se adopta**
`paho-mqtt` para no añadir dependencias sin consumidor real. Con
`VISION_CORE_EVENT_SINK_BACKEND=mqtt` el arranque falla con
`CONFIGURATION_INVALID` (`CONFIGURATION_INVALID` / `ConfigurationError`). Para
adoptarlo: implementar `MqttEventSink.send()` con QoS configurable, publicar en
`mqtt_topic` con `retain=False`, reutilizar el mismo sobre y añadir la
dependencia a `requirements.txt` y `THIRD_PARTY_NOTICES.md`.

## Verificación

```bash
python -m pytest tests/features/events tests/infrastructure/events -q
python -m pytest -q
```

Los tests cubren éxito, timeout, 5xx con reintento, 4xx permanente, duplicado
con la misma clave, dead-letter, secretos ausentes en logs y cola llena sin
bloquear el pipeline.
