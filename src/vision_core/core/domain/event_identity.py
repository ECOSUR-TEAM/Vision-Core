"""Clave de idempotencia estable de un evento, reutilizable fuera de persistencia."""

import hashlib
import json

from vision_core.core.domain.event import Event
from vision_core.core.serialization.events import event_to_json_dict


def idempotency_key_for(event: Event) -> str:
    """Devuelve ``event_id`` o un hash estable del payload serializado.

    El hash es determinista entre reinicios: dos eventos con el mismo contenido
    producen la misma clave, igual que la regla `UNIQUE(event_id)` de ADR 0002.
    """
    explicit = getattr(event, "event_id", None)
    if explicit:
        return str(explicit)
    payload = json.dumps(event_to_json_dict(event), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
