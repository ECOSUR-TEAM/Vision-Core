from dataclasses import dataclass

from domain.model.bbox import BBox


@dataclass
class Detection:
    """Salida cruda del DetectorManager para un frame."""
    bbox: BBox
    class_id: int
    confidence: float
    track_id: int  # id local asignado por el tracker (Norfair/ByteTrack), no persistente
