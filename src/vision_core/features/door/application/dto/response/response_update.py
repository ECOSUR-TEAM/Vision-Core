from dataclasses import dataclass

from vision_core.core.dto.event_payload import EventPayload


@dataclass(frozen=True, slots=True)
class ResponseUpdate:
    event: EventPayload | None
