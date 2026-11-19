import numpy as np

from vision_core.features.detection.application.dto.request.request_detector import RequestDetector
from vision_core.features.detection.application.use_cases.detect_persons import DetectPersons
from vision_core.features.detection.domain.entities.detection import Detection
from vision_core.features.detection.domain.ports.detector_manager import DetectorManager
from vision_core.shared.application.dto import BBoxPayload, DetectionPayload
from vision_core.shared.domain.bbox import BBox


class FakeDetectorManager(DetectorManager):
    def __init__(self, detections):
        self.detections = detections
        self.frames = []

    def process(self, frame):
        self.frames.append(frame)
        return self.detections

    def pop_lost_track_ids(self):
        return []


def test_detect_persons_executes_through_port_without_loading_yolo():
    frame = np.zeros((2, 2, 3), dtype=np.uint8)
    detections = [Detection(BBox(1, 2, 11, 22), 0, 0.9, 3)]
    detector = FakeDetectorManager(detections)

    response = DetectPersons(detector).execute(RequestDetector(frame))

    assert detector.frames == [frame]
    assert response.detections == (
        DetectionPayload(
            bbox=BBoxPayload(x1=1, y1=2, x2=11, y2=22),
            class_id=0,
            confidence=0.9,
            track_id=3,
        ),
    )
