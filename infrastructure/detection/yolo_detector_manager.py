import numpy as np

from domain.entities import BBox, Detection
from domain.ports import DetectorManager

PERSON_CLASS_ID = 0  # COCO
CONFIDENCE_THRESHOLD = 0.5
UNASSIGNED_TRACK_ID = -1


class YoloDetectorManager(DetectorManager):
    """VC-DETECT (Carlos + Ameth)."""

    def __init__(self, model_path: str = "yolov8n.pt") -> None:
        from ultralytics import YOLO

        self._model_path = model_path
        self._model = YOLO(model_path)

    def process(self, frame: np.ndarray) -> list[Detection]:
        result = self._model.predict(frame, verbose=False)[0]
        detections: list[Detection] = []
        for box in result.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            detections.append(
                Detection(
                    bbox=BBox(x1=x1, y1=y1, x2=x2, y2=y2),
                    class_id=int(box.cls[0]),
                    confidence=float(box.conf[0]),
                    track_id=UNASSIGNED_TRACK_ID,
                )
            )
        return detections