from abc import ABC, abstractmethod
import numpy as np

from domain.entities import Detection


class DetectorManager(ABC):
    """VC-DETECT (Carlos + Ameth): YOLOv8 + tracking (ByteTrack/Norfair).

    Debe filtrar por clase "person" (COCO) con confidence > 0.5 y
    devolver, por frame, cada detección con su track_id (id local del
    tracker, aún no persistente entre re-entradas).
    """

    @abstractmethod
    def process(self, frame: np.ndarray) -> list[Detection]:
        ...
