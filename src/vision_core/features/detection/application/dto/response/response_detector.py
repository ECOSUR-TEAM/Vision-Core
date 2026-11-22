from dataclasses import dataclass

from vision_core.core.dto.detection_payload import DetectionPayload


@dataclass(frozen=True, slots=True)
class ResponseDetector:
    """Serializable detection results."""

    detections: tuple[DetectionPayload, ...]
