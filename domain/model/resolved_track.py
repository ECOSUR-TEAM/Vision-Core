from dataclasses import dataclass

from domain.model.bbox import BBox


@dataclass
class ResolvedTrack:
    """Detection ya resuelta contra ReIDMemory (id persistente)."""
    person_id: str
    bbox: BBox
    confidence: float
    track_id: int | None = None
