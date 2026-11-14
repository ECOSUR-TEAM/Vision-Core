import os
from dataclasses import dataclass

import numpy as np

from domain.entities import BBox, Detection
from domain.ports import DetectorManager

PERSON_CLASS_ID = 0  # COCO
CONFIDENCE_THRESHOLD = 0.5
KEYPOINT_CONFIDENCE = 0.5
MIN_VISIBLE_KEYPOINTS = 4
HIP_KEYPOINT_INDICES = (11, 12)  # COCO pose: left/right hip
FRAME_EDGE_MARGIN = 10.0
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
        self._lost_ids: list[int] = []

    def process(self, frame: np.ndarray) -> list[Detection]:
        if (not isinstance(frame, np.ndarray) or frame.dtype != np.uint8
                or frame.ndim != 3 or frame.shape[2] != 3
                or min(frame.shape[:2]) <= 0):
            raise ValueError("YOLO requiere un frame BGR uint8 de forma H x W x 3")
        height, width = frame.shape[:2]
        result = self._predict(frame)
        detections: list[Detection] = []
        for index, box in enumerate(result.boxes):
            class_id = int(box.cls[0])
            confidence = float(box.conf[0])
            if class_id != PERSON_CLASS_ID or not CONFIDENCE_THRESHOLD < confidence <= 1.0:
                continue
            if not self._accepts(result, index):
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
        self._assign_tracks(detections)
        return detections

    def _predict(self, frame: np.ndarray):
        return self._model.predict(
            np.ascontiguousarray(frame), verbose=False,
            classes=[PERSON_CLASS_ID], conf=CONFIDENCE_THRESHOLD,
        )[0]

    def _accepts(self, result, index: int) -> bool:
        return True

    def pop_lost_track_ids(self) -> list[int]:
        lost, self._lost_ids = self._lost_ids, []
        return lost

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
                    self._lost_ids.append(track_id)

        for index, detection in enumerate(detections):
            if index not in matched_detections:
                detection.track_id = self._next_track_id
                self._tracks[self._next_track_id] = _Track(boxes[index], np.zeros(4))
                self._next_track_id += 1


class PosePersonDetectorManager(YoloDetectorManager):
    """Person detector backed by YOLOv8 pose keypoints.

    The pose model only knows the person class, and the keypoint filter rejects
    boxes without a human skeleton. That removes false positives such as plush
    toys or mannequins even when the box confidence is high.
    """

    def __init__(
        self,
        model_path: str = "yolov8n-pose.pt",
        min_visible_keypoints: int = MIN_VISIBLE_KEYPOINTS,
        keypoint_confidence: float = KEYPOINT_CONFIDENCE,
    ) -> None:
        if min_visible_keypoints < 1:
            raise ValueError("min_visible_keypoints debe ser >= 1")
        if not 0 < keypoint_confidence <= 1:
            raise ValueError("keypoint_confidence debe estar en (0, 1]")
        super().__init__(model_path)
        self._min_visible_keypoints = min_visible_keypoints
        self._keypoint_confidence = keypoint_confidence

    def _accepts(self, result, index: int) -> bool:
        keypoints = getattr(result, "keypoints", None)
        confidences = getattr(keypoints, "conf", None)
        if confidences is None:
            return False
        row = confidences[index]
        if hasattr(row, "detach"):
            row = row.detach().cpu().numpy()
        values = np.asarray(row, dtype=float)
        if int(np.count_nonzero(values >= self._keypoint_confidence)) < self._min_visible_keypoints:
            return False
        hips_visible = (
            values.shape[0] > max(HIP_KEYPOINT_INDICES)
            and bool(np.any(values[list(HIP_KEYPOINT_INDICES)] >= self._keypoint_confidence))
        )
        if hips_visible:
            return True
        return self._touches_frame_edge(result, index)

    @staticmethod
    def _touches_frame_edge(result, index: int) -> bool:
        shape = getattr(result, "orig_shape", None)
        boxes = getattr(result, "boxes", None)
        if shape is None or boxes is None:
            return False
        coordinates = getattr(boxes[index], "xyxy", None)
        if coordinates is None:
            return False
        coordinates = coordinates[0]
        if hasattr(coordinates, "detach"):
            coordinates = coordinates.detach().cpu().numpy()
        x1, y1, x2, y2 = [
            float(value)
            for value in np.asarray(coordinates, dtype=float).reshape(-1)[:4]
        ]
        height, width = float(shape[0]), float(shape[1])
        return (
            x1 <= FRAME_EDGE_MARGIN
            or y1 <= FRAME_EDGE_MARGIN
            or x2 >= width - FRAME_EDGE_MARGIN
            or y2 >= height - FRAME_EDGE_MARGIN
        )


def person_detector_from_env() -> DetectorManager:
    """Build the configured person detector from environment variables."""
    kind = os.getenv("VISION_CORE_PERSON_DETECTOR", "pose").strip().lower()
    if kind == "detect":
        return YoloDetectorManager(os.getenv("VISION_CORE_YOLO_MODEL", "yolov8n.pt"))
    if kind == "pose":
        return PosePersonDetectorManager(
            model_path=os.getenv("VISION_CORE_YOLO_MODEL", "yolov8n-pose.pt"),
            min_visible_keypoints=int(
                os.getenv("VISION_CORE_MIN_VISIBLE_KEYPOINTS", str(MIN_VISIBLE_KEYPOINTS))
            ),
            keypoint_confidence=float(
                os.getenv("VISION_CORE_KEYPOINT_CONFIDENCE", str(KEYPOINT_CONFIDENCE))
            ),
        )
    raise ValueError("VISION_CORE_PERSON_DETECTOR debe ser 'pose' o 'detect'")
