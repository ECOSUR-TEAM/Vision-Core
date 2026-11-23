# Sinks de eventos: entrega, idempotencia y backpressure (ECM-102)

Los eventos del pipeline pueden entregarse a sistemas externos sin bloquear la
captura. El pipeline solo conoce el puerto `EventSink`
(`src/vision_core/features/events/domain/ports/event_sink.py`); los adaptadores
concretos viven en `features/events/infrastructure/adapters`.

## Contrato

- `EventSink.send(EventEnvelope)` encola un sobre y devuelve de inmediato.
- `EventSink.close()` señala el cierre, espera hasta 2 s al worker, cuenta lo que
  no se entregó como descartado y cierra el destino y drena la cola incluso si
  el worker no terminó en ese plazo; se llama desde el `finally` del pipeline.
- `send()` posterior al cierre se contabiliza como descarte y no encola.
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
| Semántica | **Best-effort con idempotencia**, no at-least-once: una cola llena, un apagado o un dead-letter pueden perder eventos. El consumidor debe deduplicar por `Idempotency-Key`. |
| Dedupe local | Ventana LRU de `dedupe_size` claves. La clave se marca como vista **solo tras una entrega 2xx**; mientras el evento está en vuelo, un reintento se cuenta como duplicado. Descartar o enviar a dead-letter libera la clave para que el productor pueda reenviarlo. |
| Reintentos | Máximo `max_attempts` intentos; backoff `min(base * 2^(intento-1) * jitter, retry_max_seconds)`, con jitter uniforme `[1-j, 1+j]`. El tope se aplica después del jitter. |
| Errores reintentables | `PipelineError` con `retryable=True` (5xx, 408, 429, timeout, red, DNS). Se reutiliza el catálogo de ADR/errors; no hay códigos nuevos. |
| Errores permanentes | `ValidationError` con `retryable=False` (otros 4xx y redirecciones): van directo a dead-letter. |
| Dead-letter | Cola en memoria de `dead_letter_size` entradas `(EventEnvelope, code)`, consultable en tests y diagnóstico. No marca la clave como vista; no se registran payloads. |
| Cola | Acotada (`queue_size`). `send` usa `put_nowait`; con `drop-oldest` (default, ADR 0003) descarta el evento más viejo; con `drop-newest` descarta el entrante. El evento descartado libera su clave. Nunca bloquea el pipeline. |
| Apagado | `close()` señala el cierre, interrumpe reintentos/sleeps, espera hasta 2 s al worker, cuenta lo no entregado como descartado y cierra el destino y drena la cola aunque el worker siga en `send()`. |

La entrega se ejecuta en un hilo daemon distinto del pipeline. Un fallo del
destino, del callback de dead-letter o del encolado se aisla y se contabiliza;
`RunPipeline._process_frame` sigue produciendo eventos para el monitor y la
persistencia. Si encolar llega a fallar, se incrementa
`vision_core_event_sink_enqueue_failed_total`.

## Persistencia

El store de ADR 0002 se reutiliza **solo** para la identidad estable del
evento (`event_id` / `event_id_for`). No hay tabla de outbox nueva: el estado de
entrega, la ventana de dedupe, los reintentos pendientes y el dead-letter son
**en memoria**. Un evento descartado, interrumpido en el apagado o enviado a
dead-letter no queda marcado como entregado: el productor puede reenviarlo y la
misma clave derivada del payload permite al consumidor deduplicarlo. Si se
necesita durabilidad de la entrega, el siguiente paso es una tabla
`event_outbox` con `UNIQUE(event_id)` y un worker que la drene (fuera del
alcance de ECM-102).

## Configuración

Las variables se validan en `core/config/event_sink_settings.py` y se agrupan en
`Settings.events`. Errores de configuración usan `SettingsError`.

| Variable | Default | Descripción |
|---|---|---|
| `VISION_CORE_EVENT_SINK_BACKEND` | `none` | `none`, `webhook` o `mqtt`. |
| `VISION_CORE_EVENT_SINK_WEBHOOK_URL` | — | URL `http(s)://` del destino. Obligatoria para `webhook`. Sin credenciales incrustadas. |
| `VISION_CORE_EVENT_SINK_HEADERS` | `{}` | JSON objeto `{"Nombre": "valor"}`; sobrescribe headers por defecto. |
| `VISION_CORE_EVENT_SINK_TLS_VERIFY` | `1` | Verificación TLS del certificado y hostname. Al desactivarlo se emite un warning; solo en entornos controlados. |
| `VISION_CORE_EVENT_SINK_ALLOW_PRIVATE_HOSTS` | `0` | Permite literales IP privadas/loopback/link-local. Activar solo en desarrollo o pruebas. |
| `VISION_CORE_EVENT_SINK_TIMEOUT_SECONDS` | `2.0` | Timeout por petición, entre `0` y `30`. |
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
VISION_CORE_EVENT_SINK_ALLOW_PRIVATE_HOSTS=1
VISION_CORE_EVENT_SINK_HEADERS='{"Authorization": "Bearer ..."}'
VISION_CORE_EVENT_SINK_QUEUE_SIZE=128
```

## Secretos

- La URL y los valores de headers se guardan con `repr=False` y **nunca** se
  incluyen en mensajes de error, contexto ni logs: los errores informan solo
  `status`, `transport`, `code` y número de intentos.
- Se rechazan URLs con `user:password@`; los mensajes de validación nombran la
  variable, nunca su valor.
- Se rechazan destinos literales privados, CGNAT, loopback, link-local,
  multicast o no especificados salvo `ALLOW_PRIVATE_HOSTS=1`. La resolución DNS
  se valida antes de cada envío y la IP validada se fija para la conexión, sin
  una segunda resolución. El hostname original se conserva en `Host` y en SNI.
  Las redirecciones HTTP se rechazan: nunca se reenvían headers como
  `Authorization` a otro host.
- Los mensajes pasan por la taxonomía `VisionCoreError` → `sanitize_context()`,
  que descarta claves como `authorization`, `token`, `url` o `password`.
- Para rotar credenciales, inyecta el secreto por entorno en
  `VISION_CORE_EVENT_SINK_HEADERS`; no lo escribas en `.env` versionado.

## Observabilidad

Métricas en `/metrics` (prefijo `vision_core_event_sink_`):

| Métrica | Significado |
|---|---|
| `vision_core_event_sink_submitted_total` | Llamadas a `send`, incluidos duplicados y descartes. |
| `vision_core_event_sink_delivered_total` | Entregas confirmadas (2xx). |
| `vision_core_event_sink_retried_total` | Reintentos realizados. |
| `vision_core_event_sink_dropped_total` | Eventos descartados por cola llena, cierre o `send()` posterior al cierre. |
| `vision_core_event_sink_duplicate_total` | Claves suprimidas por idempotencia. |
| `vision_core_event_sink_dead_letter_total` | Eventos agotados o permanentes. |
| `vision_core_event_sink_enqueue_failed_total` | Fallos al encolar desde el pipeline; el evento no llega al dispatcher. |
| `vision_core_event_sink_queue_depth` | Profundidad actual de la cola (gauge). |

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
python -m pytest -q -m "not slow" --cov=vision_core --cov-branch \
  --cov-fail-under=80
PYTHONPATH=src python -m vision_core.scripts.check_coverage coverage.json
```

Los tests cubren éxito, timeout, 5xx/408/429 con reintento, 4xx permanente,
redirecciones rechazadas, hosts no públicos, duplicado con la misma clave,
reintento tras descarte o dead-letter, apagado, secretos ausentes en logs y cola
llena sin bloquear el pipeline.
