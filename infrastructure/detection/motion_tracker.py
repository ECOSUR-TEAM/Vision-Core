from dataclasses import dataclass

import numpy as np

from domain.model.detection import Detection

from .iou import iou

MATCH_IOU_THRESHOLD = 0.3
MAX_MISSED_FRAMES = 30


@dataclass
class _Track:
    bbox: np.ndarray
    velocity: np.ndarray
    missed: int = 0

    def predict(self) -> np.ndarray:
        return self.bbox + self.velocity * (self.missed + 1)


class MotionTracker:
    """Assign local IDs using motion prediction and IoU association."""

    def __init__(self) -> None:
        self._tracks: dict[int, _Track] = {}
        self._next_track_id = 1
        self._lost_ids: list[int] = []

    def update(self, detections: list[Detection]) -> None:
        boxes = [
            np.array([d.bbox.x1, d.bbox.y1, d.bbox.x2, d.bbox.y2], dtype=float)
            for d in detections
        ]
        candidates = []
        for track_id, track in self._tracks.items():
            prediction = track.predict()
            for index, bbox in enumerate(boxes):
                overlap = iou(prediction, bbox)
                if overlap >= MATCH_IOU_THRESHOLD:
                    candidates.append((-overlap, track_id, index))

        matched_tracks: set[int] = set()
        matched_detections: set[int] = set()
        for _, track_id, index in sorted(candidates):
            if track_id in matched_tracks or index in matched_detections:
                continue
            track = self._tracks[track_id]
            track.velocity = (boxes[index] - track.bbox) / (track.missed + 1)
            track.bbox = boxes[index]
            track.missed = 0
            detections[index].track_id = track_id
            matched_tracks.add(track_id)
            matched_detections.add(index)

        for track_id in list(self._tracks):
            if track_id not in matched_tracks:
                self._tracks[track_id].missed += 1
                if self._tracks[track_id].missed > MAX_MISSED_FRAMES:
                    del self._tracks[track_id]
                    self._lost_ids.append(track_id)

        for index, detection in enumerate(detections):
            if index not in matched_detections:
                detection.track_id = self._next_track_id
                self._tracks[self._next_track_id] = _Track(boxes[index], np.zeros(4))
                self._next_track_id += 1

    def pop_lost_track_ids(self) -> list[int]:
        lost, self._lost_ids = self._lost_ids, []
        return lost
