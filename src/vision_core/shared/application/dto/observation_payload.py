"""Zone observation payload returned by the door feature."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ObservationPayload:
    position: tuple[float, float]
    zone: str
    timestamp: float
