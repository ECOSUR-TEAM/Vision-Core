from dataclasses import dataclass

from vision_core.shared.domain.bbox import BBox


@dataclass
class ResolvedTrack:
    person_id: str
    bbox: BBox
    confidence: float
    track_id: int | None = None
