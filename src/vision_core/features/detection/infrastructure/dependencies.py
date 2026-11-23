from dataclasses import dataclass

from vision_core.core.config import Settings
from vision_core.core.model_registry.model_descriptor import ModelDescriptor
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
    model_path: str | None = None,
    device: str | None = None,
    precision: str | None = None,
    confidence: float | None = None,
    classes: tuple[int, ...] | None = None,
    tracking_enabled: bool | None = None,
    max_missed_frames: int | None = None,
    model_descriptor: ModelDescriptor | None = None,
) -> DetectionDependencies:
    """Build the detection use case with an injectable adapter."""

    if detector is None:
        settings = Settings.from_env(validate_startup=False).detection
        detector = YoloDetectorManager(
            model_path or str(settings.model_path),
            device=device if device is not None else settings.device,
            precision=precision if precision is not None else settings.precision,
            confidence=confidence if confidence is not None else settings.confidence,
            classes=classes if classes is not None else settings.classes,
            tracking_enabled=tracking_enabled if tracking_enabled is not None else settings.tracking_enabled,
            max_missed_frames=max_missed_frames if max_missed_frames is not None else settings.max_missed_frames,
            model_descriptor=model_descriptor,
        )
    return DetectionDependencies(detector=detector, detect_persons=DetectPersons(detector))
