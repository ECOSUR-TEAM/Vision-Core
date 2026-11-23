"""Sobre serializable para entrega de eventos a sinks externos (ECM-102).

El ``payload`` conserva el contrato de eventos de ticket 31; ``event_id``
viaja fuera del payload como clave de idempotencia de la entrega.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from vision_core.core.serialization.json_value import JSONValue


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    event_id: str
    payload: Mapping[str, JSONValue]
