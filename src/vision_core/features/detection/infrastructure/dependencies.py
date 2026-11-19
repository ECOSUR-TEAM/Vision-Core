from dataclasses import dataclass

from vision_core.features.detection.application.use_cases.detect_persons import DetectPersons
from vision_core.features.detection.domain.ports.detector_manager import DetectorManager
from vision_core.features.detection.infrastructure.adapters.yolo_detector_manager import (
    YoloDetectorManager,
)
from vision_core.settings import Settings


@dataclass(frozen=True)
class DetectionDependencies:
    detector: DetectorManager
    detect_persons: DetectPersons


def build_detection(
    detector: DetectorManager | None = None,
    *,
    model_path: str | None = None,
    device: str | None = None,
    confidence: float | None = None,
    classes: tuple[int, ...] | None = None,
    tracking_enabled: bool | None = None,
    max_missed_frames: int | None = None,
) -> DetectionDependencies:
    """Build the detection use case with an injectable adapter."""

    if detector is None:
        settings = Settings.from_env(validate_startup=False).detection
        detector = YoloDetectorManager(
            model_path or str(settings.model_path),
            device=device if device is not None else settings.device,
            confidence=confidence if confidence is not None else settings.confidence,
            classes=classes if classes is not None else settings.classes,
            tracking_enabled=tracking_enabled if tracking_enabled is not None else settings.tracking_enabled,
            max_missed_frames=max_missed_frames if max_missed_frames is not None else settings.max_missed_frames,
        )
    return DetectionDependencies(detector=detector, detect_persons=DetectPersons(detector))
    return DetectionDependencies(detector=detector, detect_persons=DetectPersons(detector))
