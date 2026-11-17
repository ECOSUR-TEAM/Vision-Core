from abc import ABC, abstractmethod
from typing import Any

from vision_core.features.detection.domain.entities.detection import Detection


class DetectorManager(ABC):
    """Port for person detection and local track assignment."""

    @abstractmethod
    def process(self, frame: Any) -> list[Detection]:
        ...

    @abstractmethod
    def pop_lost_track_ids(self) -> list[int]:
        ...
