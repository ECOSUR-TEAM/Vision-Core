"""Composición del sink de eventos: el pipeline solo recibe el puerto."""

from vision_core.core.config.event_sink_settings import EventSinkSettings
from vision_core.core.errors import ConfigurationError
from vision_core.core.telemetry.metrics import ObservabilityMetrics
from vision_core.features.events.application.use_cases.dispatch_events import EventSinkDispatcher
from vision_core.features.events.domain.ports.event_sink import EventSink
from vision_core.features.events.infrastructure.adapters.mqtt_event_sink import MqttEventSink
from vision_core.features.events.infrastructure.adapters.webhook_event_sink import WebhookEventSink


def build_event_sink(
    settings: EventSinkSettings,
    *,
    metrics: ObservabilityMetrics | None = None,
) -> EventSinkDispatcher | None:
    """Devuelve el despachante o ``None`` cuando el backend está desactivado."""
    if settings.backend == "none":
        return None
    destination: EventSink
    if settings.backend == "webhook":
        destination = WebhookEventSink(settings)
    elif settings.backend == "mqtt":
        destination = MqttEventSink(settings)
    else:
        raise ConfigurationError("VISION_CORE_EVENT_SINK_BACKEND: backend no soportado")
    return EventSinkDispatcher(destination, settings, metrics=metrics)
