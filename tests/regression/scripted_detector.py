from vision_core.features.detection.domain.entities.detection import Detection
from vision_core.features.detection.domain.ports.detector_manager import DetectorManager


class ScriptedDetector(DetectorManager):
    def __init__(self, frames: list[list[Detection]], lost_ids: list[list[int]] | None = None) -> None:
        self._frames = list(frames)
        self._lost_ids = [list(ids) for ids in (lost_ids or [[] for _ in frames])]
        self._index = 0

    @property
    def frame_index(self) -> int:
        return max(0, self._index - 1)

    def process(self, frame) -> list[Detection]:
        detections = self._frames[self._index]
        self._index += 1
        return list(detections)

    def pop_lost_track_ids(self) -> list[int]:
        ids = self._lost_ids[self._index - 1] if self._index else []
        return list(ids)
