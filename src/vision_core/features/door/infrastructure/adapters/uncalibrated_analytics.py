from vision_core.core.domain.event import Event
from vision_core.features.door.domain.entities.zone_observation import ZoneObservation
from vision_core.features.door.domain.ports.door_analytics import DoorAnalytics


class UncalibratedAnalytics(DoorAnalytics):
    def update(self, person_id: str, position: tuple[float, float]) -> Event | None:
        return None

    def get_history(self, person_id: str) -> tuple[ZoneObservation, ...]:
        return ()
