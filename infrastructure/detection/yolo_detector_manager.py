import numpy as np

from domain.entities import BBox, Detection
from domain.ports import DetectorManager

from .motion_tracker import MAX_MISSED_FRAMES, MotionTracker

PERSON_CLASS_ID = 0  # COCO
CONFIDENCE_THRESHOLD = 0.5
UNASSIGNED_TRACK_ID = -1


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
        self._tracker = MotionTracker()

    def process(self, frame: np.ndarray) -> list[Detection]:
        if (not isinstance(frame, np.ndarray) or frame.dtype != np.uint8
                or frame.ndim != 3 or frame.shape[2] != 3
                or min(frame.shape[:2]) <= 0):
            raise ValueError("YOLO requiere un frame BGR uint8 de forma H x W x 3")
        height, width = frame.shape[:2]
        result = self._model.predict(
            np.ascontiguousarray(frame), verbose=False,
            classes=[PERSON_CLASS_ID], conf=CONFIDENCE_THRESHOLD,
        )[0]
        detections: list[Detection] = []
        for box in result.boxes:
            class_id = int(box.cls[0])
            confidence = float(box.conf[0])
            if class_id != PERSON_CLASS_ID or not CONFIDENCE_THRESHOLD < confidence <= 1.0:
                continue
            coordinates = np.asarray(box.xyxy[0].tolist(), dtype=float)
            if coordinates.shape != (4,) or not np.isfinite(coordinates).all():
                continue
            x1, y1, x2, y2 = coordinates.tolist()
            x1, x2 = max(0.0, min(x1, width)), max(0.0, min(x2, width))
            y1, y2 = max(0.0, min(y1, height)), max(0.0, min(y2, height))
            if x2 <= x1 or y2 <= y1:
                continue
            detections.append(
                Detection(
                    bbox=BBox(x1=x1, y1=y1, x2=x2, y2=y2),
                    class_id=class_id,
                    confidence=confidence,
                    track_id=UNASSIGNED_TRACK_ID,
                )
            )
        self._tracker.update(detections)
        return detections

    def pop_lost_track_ids(self) -> list[int]:
        return self._tracker.pop_lost_track_ids()
