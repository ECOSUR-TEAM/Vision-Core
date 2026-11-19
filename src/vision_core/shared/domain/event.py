import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from vision_core.shared.domain.event_type import EventType


@dataclass
class Event:
    event: str
    person_id: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        self.event = EventType(self.event).value
        self.person_id = str(self.person_id)
        self.timestamp = float(self.timestamp)
