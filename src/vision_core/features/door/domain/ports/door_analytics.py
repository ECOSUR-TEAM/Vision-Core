from abc import ABC, abstractmethod
from typing import Optional

from vision_core.core.domain.event import Event
from vision_core.features.door.domain.entities.zone_observation import ZoneObservation


class DoorAnalytics(ABC):
    @abstractmethod
    def update(self, person_id: str, position: tuple[float, float]) -> Optional[Event]: ...

    @abstractmethod
    def get_history(self, person_id: str) -> tuple[ZoneObservation, ...]: ...
