"""Mappers between pipeline domain entities and transport DTOs."""

from vision_core.core.dto.bbox_payload import BBoxPayload
from vision_core.core.dto.resolved_track_payload import ResolvedTrackPayload
from vision_core.core.validation import bounded_int, finite_bbox, finite_unit_float, required_str
from vision_core.features.pipeline.domain.entities.resolved_track import ResolvedTrack

__all__ = ["resolved_track_to_dto"]


def resolved_track_to_dto(track: ResolvedTrack) -> ResolvedTrackPayload:
    return ResolvedTrackPayload(
        person_id=required_str(track.person_id, "person_id"),
        bbox=BBoxPayload(*finite_bbox(track.bbox)),
        confidence=finite_unit_float(track.confidence, "confidence"),
        track_id=None if track.track_id is None else bounded_int(track.track_id, "track_id"),
    )
