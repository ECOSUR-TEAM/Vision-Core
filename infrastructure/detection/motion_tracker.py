"""Compatibility imports for the detection tracking adapter."""

from vision_core.features.detection.infrastructure.adapters.motion_tracker import (
    MATCH_IOU_THRESHOLD,
    MAX_MISSED_FRAMES,
    MotionTracker,
)

__all__ = ["MATCH_IOU_THRESHOLD", "MAX_MISSED_FRAMES", "MotionTracker"]
