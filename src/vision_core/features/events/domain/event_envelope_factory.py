"""Conversión de eventos de dominio a sobres listos para transporte."""

from vision_core.core.domain.event import Event
from vision_core.core.domain.event_identity import idempotency_key_for
from vision_core.core.dto.event_envelope import EventEnvelope
from vision_core.core.serialization.event_serializer import event_to_json_dict


def envelope_for(event: Event) -> EventEnvelope:
    """Construye el sobre sin alterar el formato de evento del ticket 31."""
    return EventEnvelope(event_id=idempotency_key_for(event), payload=event_to_json_dict(event))
