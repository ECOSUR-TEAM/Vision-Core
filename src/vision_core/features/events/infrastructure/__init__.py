"""Infraestructura del slice de eventos."""

from vision_core.features.events.application.use_cases.dispatch_events import EventSinkDispatcher
from vision_core.features.events.infrastructure.dependencies import build_event_sink

__all__ = ["EventSinkDispatcher", "build_event_sink"]
