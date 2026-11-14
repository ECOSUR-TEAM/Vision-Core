"""Zone configuration model."""
from dataclasses import dataclass

from domain.entities import Polygon


@dataclass(frozen=True)
class ZoneConfig:
    width: int
    height: int
    door: Polygon
    exterior: Polygon
    interior: Polygon
