from typing import NamedTuple


class ZoneObservation(NamedTuple):
    position: tuple[float, float]
    zone: str
    timestamp: float
