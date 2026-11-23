# Eventos: sinks salientes

Este slice define el puerto de salida `EventSink` y su entrega idempotente. El
pipeline de visión solo conoce el puerto; los adaptadores concretos viven aquí.

- [Contrato, semántica de entrega, configuración y observabilidad](../../../../docs/event-sinks.md)
- [ADR 0010](../../../../docs/adr/0010-sinks-de-eventos-y-entrega-idempotente.md)

Puntos de entrada:

- `domain/ports/event_sink.py`: contrato `EventSink`.
- `domain/event_envelope_factory.py`: evento de dominio → sobre serializable.
- `application/use_cases/dispatch_events.py`: cola acotada, dedupe, reintentos
  y dead-letter.
- `infrastructure/adapters/webhook_event_sink.py`: primer destino soportado.
- `infrastructure/adapters/mqtt_event_sink.py`: puerto reservado, detrás de flag.
