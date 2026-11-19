"""Event payload shared by door and monitor responses."""

from collections.abc import Mapping
from dataclasses import dataclass

from vision_core.shared.application.dto.json_value import JSONValue


@dataclass(frozen=True, slots=True)
class EventPayload:
    event: str
    person_id: str
    timestamp: float
    metadata: Mapping[str, JSONValue]
