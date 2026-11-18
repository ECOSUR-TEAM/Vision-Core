from vision_core.features.detection.application.use_cases.detect_persons import DetectPersons
from vision_core.features.detection.domain.ports.detector_manager import DetectorManager
from vision_core.features.detection.infrastructure.adapters.yolo_detector_manager import (
    YoloDetectorManager,
)


def build_detection(
    detector: DetectorManager | None = None,
    *,
    model_path: str = "yolov8n.pt",
) -> DetectPersons:
    """Build the detection use case with an injectable adapter."""

    if detector is None:
        detector = YoloDetectorManager(model_path)
    return DetectPersons(detector)
