"""Immutable snapshot of a tracking result handed to the renderer thread."""

from dataclasses import dataclass

from vision_core.shared.domain.bbox import BBox


@dataclass(frozen=True, slots=True)
class RenderTrack:
    """Copia congelada: el hilo de inferencia puede reutilizar sus objetos después."""

    person_id: str
    bbox: BBox
    confidence: float
    track_id: int | None

    @classmethod
    def from_track(cls, track) -> "RenderTrack":
        return cls(
            person_id=str(track.person_id),
            bbox=track.bbox,
            confidence=float(track.confidence),
            track_id=track.track_id,
        )
