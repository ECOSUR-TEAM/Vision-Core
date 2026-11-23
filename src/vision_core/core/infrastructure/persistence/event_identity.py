"""Compatibilidad de la persistencia con la clave de idempotencia compartida."""

from vision_core.core.domain.event import Event
from vision_core.core.domain.event_identity import idempotency_key_for


def event_id_for(event: Event) -> str:
    return idempotency_key_for(event)
