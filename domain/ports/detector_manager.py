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

    @abstractmethod
    def pop_lost_track_ids(self) -> list[int]:
        """track_id locales descartados definitivamente desde la última
        llamada (superaron el máximo de frames perdidos). El llamador
        debe usarlos para avisar a ReIDMemory (mark_lost) antes de que
        el id se reutilice para otra persona. Vacía el buffer interno."""
        ...
