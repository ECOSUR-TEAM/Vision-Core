"""Puerto MQTT reservado: no se adopta dependencia hasta que haya consumidor real."""

from vision_core.core.config.event_sink_settings import EventSinkSettings
from vision_core.core.dto.event_envelope import EventEnvelope
from vision_core.core.errors import ConfigurationError


class MqttEventSink:
    """Implementación futura de ``EventSink`` sobre MQTT (ECM-102).

    El backend MQTT queda detrás de ``VISION_CORE_EVENT_SINK_BACKEND=mqtt``.
    Hoy no se instala ``paho-mqtt`` para no agregar dependencias innecesarias;
    al activarlo se falla tempranamente con ``CONFIGURATION_INVALID``.
    """

    def __init__(self, settings: EventSinkSettings) -> None:
        if not settings.mqtt_host or not settings.mqtt_topic:
            raise ConfigurationError("MQTT: host y topic son obligatorios")
        raise ConfigurationError(
            "MQTT no disponible en esta build; use backend=webhook o añada el adaptador con paho-mqtt"
        )

    def send(self, envelope: EventEnvelope) -> None:
        raise ConfigurationError("MQTT no disponible en esta build")

    def close(self) -> None:
        return None
