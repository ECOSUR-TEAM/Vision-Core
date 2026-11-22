"""Single detection payload returned by the detection feature."""

from dataclasses import dataclass

from vision_core.core.dto.bbox_payload import BBoxPayload


@dataclass(frozen=True, slots=True)
class DetectionPayload:
    bbox: BBoxPayload
    class_id: int
    confidence: float
    track_id: int | None
