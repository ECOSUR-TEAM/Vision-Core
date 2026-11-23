"""Slice de eventos: entrega saliente idempotente con backpressure (ECM-102)."""

from vision_core.features.events.domain import EventEnvelope, EventSink, envelope_for

__all__ = ["EventEnvelope", "EventSink", "envelope_for"]
