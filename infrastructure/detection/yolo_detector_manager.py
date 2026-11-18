"""Compatibility import for the detection adapter."""

from vision_core.features.detection.infrastructure.adapters.yolo_detector_manager import (
    CONFIDENCE_THRESHOLD,
    PERSON_CLASS_ID,
    UNASSIGNED_TRACK_ID,
    YoloDetectorManager,
)

__all__ = [
    "CONFIDENCE_THRESHOLD",
    "PERSON_CLASS_ID",
    "UNASSIGNED_TRACK_ID",
    "YoloDetectorManager",
]
