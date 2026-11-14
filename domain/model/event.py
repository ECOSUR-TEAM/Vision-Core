import time
from dataclasses import dataclass, field
from typing import Any

from domain.model.event_type import EventType


@dataclass
class Event:
    event: str  # EventType: "PERSON_ENTERED" | "PERSON_EXITED" | "FALSE_ALARM"
    person_id: str
    timestamp: float = field(default_factory=time.time)  # epoch en segundos
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.event = EventType(self.event).value  # ValueError si el nombre no es válido
        self.person_id = str(self.person_id)
        self.timestamp = float(self.timestamp)
