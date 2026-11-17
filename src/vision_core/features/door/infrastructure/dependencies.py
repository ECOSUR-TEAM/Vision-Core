from dataclasses import dataclass
from pathlib import Path

from vision_core.features.door.application.use_cases.get_history import GetHistory
from vision_core.features.door.application.use_cases.update_zone import UpdateZone
from vision_core.features.door.domain.ports.door_analytics import DoorAnalytics
from vision_core.features.door.infrastructure.adapters.polygon_door_analytics import PolygonDoorAnalytics
from vision_core.features.door.infrastructure.adapters.uncalibrated_analytics import UncalibratedAnalytics
from vision_core.features.door.infrastructure.config.zone_loader import load_zones


@dataclass(frozen=True)
class DoorUseCases:
    update_zone: UpdateZone
    get_history: GetHistory


def build_door(
    zones_path: str | Path | None = None,
    *,
    confirmation_frames: int = 3,
    history_limit: int = 300,
    analytics: DoorAnalytics | None = None,
) -> DoorUseCases:
    if analytics is None:
        if zones_path is None:
            analytics = UncalibratedAnalytics()
        else:
            zones = load_zones(zones_path)
            analytics = PolygonDoorAnalytics(
                zones.exterior,
                zones.interior,
                zones.door,
                confirmation_frames=confirmation_frames,
                history_limit=history_limit,
            )
    return DoorUseCases(UpdateZone(analytics), GetHistory(analytics))
