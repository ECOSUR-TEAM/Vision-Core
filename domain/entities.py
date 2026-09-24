import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np


@dataclass(frozen=True)
class BBox:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)


@dataclass
class Detection:
    """Salida cruda del DetectorManager para un frame."""
    bbox: BBox
    class_id: int
    confidence: float
    track_id: int  # id local asignado por el tracker (Norfair/ByteTrack), no persistente


@dataclass
class ResolvedTrack:
    """Detection ya resuelta contra ReIDMemory (id persistente)."""
    person_id: str
    bbox: BBox
    confidence: float


class EventType(str, Enum):
    PERSON_ENTERED = "PERSON_ENTERED"
    PERSON_EXITED = "PERSON_EXITED"
    FALSE_ALARM = "FALSE_ALARM"


def _jsonable(value: Any) -> Any:
    """Convierte a tipos nativos de JSON (numpy, tuplas, enums, etc.)."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": self.event,
            "person_id": self.person_id,
            "timestamp": self.timestamp,
            "metadata": _jsonable(self.metadata),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


@dataclass(frozen=True)
class Polygon:
    """Zona ROI (exterior/interior) como lista de puntos (x, y)."""
    name: str
    points: tuple[tuple[float, float], ...]