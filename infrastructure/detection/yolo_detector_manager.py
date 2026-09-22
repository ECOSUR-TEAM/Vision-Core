from dataclasses import dataclass

import numpy as np

from domain.entities import BBox, Detection
from domain.ports import DetectorManager

PERSON_CLASS_ID = 0  # COCO
CONFIDENCE_THRESHOLD = 0.5
UNASSIGNED_TRACK_ID = -1
MATCH_IOU_THRESHOLD = 0.3
MAX_MISSED_FRAMES = 30


@dataclass
class _Track:
    bbox: np.ndarray
    velocity: np.ndarray
    missed: int = 0

    def predict(self) -> np.ndarray:
        return self.bbox + self.velocity * (self.missed + 1)


def _iou(first: np.ndarray, second: np.ndarray) -> float:
    intersection = np.maximum(
        np.minimum(first[2:], second[2:]) - np.maximum(first[:2], second[:2]), 0
    ).prod()
    union = (
        np.maximum(first[2:] - first[:2], 0).prod()
        + np.maximum(second[2:] - second[:2], 0).prod()
        - intersection
    )
    return float(intersection / union) if union > 0 else 0.0


class YoloDetectorManager(DetectorManager):
    """Person detection with local motion/IoU tracking for one video stream.

    Reuse the instance across frames; create a new instance for another stream.
    Tracks survive up to MAX_MISSED_FRAMES absent detections. Only current
    detections are returned, never extrapolated boxes. This lightweight tracker
    has no appearance model, so ambiguous overlaps can still switch identities.
    """

    def __init__(self, model_path: str = "yolov8n.pt") -> None:
        from ultralytics import YOLO

        self._model_path = model_path
        self._model = YOLO(model_path)
        self._tracks: dict[int, _Track] = {}
        self._next_track_id = 1

    def process(self, frame: np.ndarray) -> list[Detection]:
        result = self._model.predict(frame, verbose=False)[0]
        detections: list[Detection] = []
        for box in result.boxes:
            class_id = int(box.cls[0])
            confidence = float(box.conf[0])
            if class_id != PERSON_CLASS_ID or not confidence > CONFIDENCE_THRESHOLD:
                continue
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            detections.append(
                Detection(
                    bbox=BBox(x1=x1, y1=y1, x2=x2, y2=y2),
                    class_id=class_id,
                    confidence=confidence,
                    track_id=UNASSIGNED_TRACK_ID,
                )
            )
        self._assign_tracks(detections)
        return detections

    def _assign_tracks(self, detections: list[Detection]) -> None:
        boxes = [
            np.array([d.bbox.x1, d.bbox.y1, d.bbox.x2, d.bbox.y2], dtype=float)
            for d in detections
        ]
        # Associate strongest overlaps first, using each track/detection once.
        candidates = []
        for track_id, track in self._tracks.items():
            prediction = track.predict()
            for index, bbox in enumerate(boxes):
                overlap = _iou(prediction, bbox)
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

        for index, detection in enumerate(detections):
            if index not in matched_detections:
                detection.track_id = self._next_track_id
                self._tracks[self._next_track_id] = _Track(boxes[index], np.zeros(4))
                self._next_track_id += 1
