"""Zone configuration model."""
from dataclasses import dataclass

from vision_core.domain.model.polygon import Polygon


@dataclass(frozen=True)
class ZoneConfig:
    width: int
    height: int
    door: Polygon
    exterior: Polygon
    interior: Polygon
