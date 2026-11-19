from dataclasses import dataclass

from vision_core.features.detection.application.use_cases.detect_persons import DetectPersons
from vision_core.features.detection.domain.ports.detector_manager import DetectorManager
from vision_core.features.detection.infrastructure.adapters.yolo_detector_manager import (
    YoloDetectorManager,
)


@dataclass(frozen=True)
class DetectionDependencies:
    detector: DetectorManager
    detect_persons: DetectPersons


def build_detection(
    detector: DetectorManager | None = None,
    *,
    model_path: str = "yolov8n.pt",
    confidence: float = 0.5,
    classes: tuple[int, ...] = (0,),
    tracking_enabled: bool = True,
    max_missed_frames: int = 30,
) -> DetectionDependencies:
    """Build the detection use case with an injectable adapter."""

    if detector is None:
        detector = YoloDetectorManager(
            model_path,
            confidence=confidence,
            classes=classes,
            tracking_enabled=tracking_enabled,
            max_missed_frames=max_missed_frames,
        )
    return DetectionDependencies(detector=detector, detect_persons=DetectPersons(detector))
