"""Dominio del slice de eventos: contrato de salida y sobre serializable."""

from vision_core.core.dto.event_envelope import EventEnvelope
from vision_core.features.events.domain.event_envelope_factory import envelope_for
from vision_core.features.events.domain.ports import EventSink

__all__ = ["EventEnvelope", "EventSink", "envelope_for"]
