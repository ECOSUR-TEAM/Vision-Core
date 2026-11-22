from dataclasses import dataclass

from vision_core.core.domain.bbox import BBox


@dataclass
class Detection:
    """Salida cruda del detector para un frame."""

    bbox: BBox
    class_id: int
    confidence: float
    track_id: int
