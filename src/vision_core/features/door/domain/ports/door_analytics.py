from abc import ABC, abstractmethod

from vision_core.features.door.domain.entities.zone_observation import ZoneObservation
from vision_core.shared.domain.event import Event


class DoorAnalytics(ABC):
    @abstractmethod
    def update(self, person_id: str, position: tuple[float, float]) -> Event | None:
        ...

    @abstractmethod
    def get_history(self, person_id: str) -> tuple[ZoneObservation, ...]:
        ...
