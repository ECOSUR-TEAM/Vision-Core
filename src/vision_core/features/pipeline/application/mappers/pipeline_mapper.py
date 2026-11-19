"""Mappers between pipeline domain entities and transport DTOs."""

from vision_core.features.pipeline.application.dto.response.response_pipeline_event import ResponsePipelineEvent
from vision_core.features.pipeline.domain.entities.resolved_track import ResolvedTrack
from vision_core.shared.application.dto.bbox_payload import BBoxPayload
from vision_core.shared.application.dto.json_value import JSONValue
from vision_core.shared.application.dto.resolved_track_payload import ResolvedTrackPayload
from vision_core.shared.application.dto.serialization import dumps_json, to_json_value
from vision_core.shared.application.validation import (
    bounded_int,
    finite_bbox,
    finite_float,
    finite_unit_float,
    json_metadata,
    required_str,
)
from vision_core.shared.domain.event import Event

__all__ = [
    "event_to_dict",
    "event_to_dto",
    "event_to_json",
    "resolved_track_to_dto",
]


def event_to_dto(event: Event) -> ResponsePipelineEvent:
    return ResponsePipelineEvent(
        event=required_str(event.event, "event"),
        person_id=required_str(event.person_id, "person_id"),
        timestamp=finite_float(event.timestamp, "timestamp"),
        metadata=json_metadata(event.metadata),
    )


def event_to_dict(event: Event) -> dict[str, JSONValue]:
    payload = to_json_value(event_to_dto(event))
    if not isinstance(payload, dict):
        raise ValueError("Event DTO must serialize to a JSON object")
    return payload


def event_to_json(event: Event) -> str:
    try:
        return dumps_json(event_to_dto(event))
    except ValueError as exc:
        raise ValueError(f"Cannot serialize event {event.event!r} as JSON: {exc}") from exc


def resolved_track_to_dto(track: ResolvedTrack) -> ResolvedTrackPayload:
    return ResolvedTrackPayload(
        person_id=required_str(track.person_id, "person_id"),
        bbox=BBoxPayload(*finite_bbox(track.bbox)),
        confidence=finite_unit_float(track.confidence, "confidence"),
        track_id=None if track.track_id is None else bounded_int(track.track_id, "track_id"),
    )
