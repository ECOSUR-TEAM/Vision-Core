"""Puerto de salida de eventos: el pipeline solo conoce este contrato."""

from typing import Protocol

from vision_core.core.dto.event_envelope import EventEnvelope


class EventSink(Protocol):
    """Destino de eventos con entrega explícita y no bloqueante.

    La implementación compuesta (``EventSinkDispatcher``) decide cuándo llamar
    a ``send``; los adaptadores concretos solo intentan una entrega.
    """

    def send(self, envelope: EventEnvelope) -> None:
        """Entrega un sobre. Puede lanzar errores de la taxonomía de Vision Core."""
        ...

    def close(self) -> None:
        """Libera recursos y drena la cola acotada si la implementación la usa."""
        ...
