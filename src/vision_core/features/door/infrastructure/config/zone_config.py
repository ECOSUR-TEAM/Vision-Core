from dataclasses import dataclass

from vision_core.core.domain.polygon import Polygon


@dataclass(frozen=True)
class ZoneConfig:
    width: int
    height: int
    door: Polygon
    exterior: Polygon
    interior: Polygon
