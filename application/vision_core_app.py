from typing import Callable, Optional
import numpy as np

from domain.entities import Event
from domain.ports import VideoSource, DetectorManager, ReIDMemory, DoorAnalytics


class VisionCoreApp:
    """VC-APP (Fabricio): orquesta el pipeline completo.

    video -> DetectorManager -> ReIDMemory -> DoorAnalytics -> Event

    Depende solo de los ports (domain.ports), nunca de una implementación
    concreta: eso permite testear con mocks y que cada módulo avance
    en paralelo sin acoplarse a los demás.
    """

    def __init__(
        self,
        video_source: VideoSource,
        detector: DetectorManager,
        reid_memory: ReIDMemory,
        door_analytics: DoorAnalytics,
        embedder: Callable[[np.ndarray], np.ndarray],
        on_event: Callable[[Event], None],
    ) -> None:
        self._video = video_source
        self._detector = detector
        self._reid = reid_memory
        self._door = door_analytics
        self._embed = embedder
        self._on_event = on_event

    def run(self) -> None:
        self._video.open()
        try:
            while True:
                frame = self._video.read_frame()
                if frame is None:
                    break
                self._process_frame(frame)
        finally:
            self._video.close()

    def _process_frame(self, frame: np.ndarray) -> None:
        for det in self._detector.process(frame):
            crop = frame[
                int(det.bbox.y1):int(det.bbox.y2),
                int(det.bbox.x1):int(det.bbox.x2),
            ]
            embedding = self._embed(crop)
            person_id = self._reid.resolve(det.track_id, embedding, det.bbox)

            event = self._door.update(person_id, det.bbox.center)
            if event is not None:
                self._on_event(event)
