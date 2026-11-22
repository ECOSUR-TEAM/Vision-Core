"""Resolved track payload returned by the pipeline feature."""

from dataclasses import dataclass

from vision_core.core.dto.bbox_payload import BBoxPayload


@dataclass(frozen=True, slots=True)
class ResolvedTrackPayload:
    person_id: str
    bbox: BBoxPayload
    confidence: float
    track_id: int | None
