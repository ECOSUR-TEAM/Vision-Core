"""Zone configuration model."""

from dataclasses import dataclass

from domain.model.polygon import Polygon


@dataclass(frozen=True)
class ZoneConfig:
    width: int
    height: int
    door: Polygon
    exterior: Polygon
    interior: Polygon
