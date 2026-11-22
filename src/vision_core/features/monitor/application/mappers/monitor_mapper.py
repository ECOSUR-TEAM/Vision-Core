"""Mappers between monitor state snapshots and transport DTOs."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from vision_core.core.dto import EVENT_SCHEMA_VERSION
from vision_core.core.dto.bbox_payload import BBoxPayload
from vision_core.core.dto.event_payload import EventPayload
from vision_core.core.dto.monitor_person_payload import MonitorPersonPayload
from vision_core.core.validation import (
    bounded_int,
    finite_bbox,
    finite_float,
    json_metadata,
    required_str,
)
from vision_core.features.monitor.application.dto.response.response_frame import ResponseFrame
from vision_core.features.monitor.application.dto.response.response_snapshot import ResponseSnapshot


def _person_payload(value: Any) -> MonitorPersonPayload:
    if isinstance(value, MonitorPersonPayload):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("people entries must be MonitorPersonPayload or mappings")
    bbox = value.get("bbox")
    confidence = value.get("confidence")
    track_id = value.get("track_id")
    zone = value.get("zone")
    display_name = value.get("display_name")
    return MonitorPersonPayload(
        person_id=required_str(value.get("person_id"), "people.person_id"),
        bbox=None if bbox is None else BBoxPayload(*finite_bbox(bbox, "people.bbox")),
        confidence=None if confidence is None else finite_float(confidence, "people.confidence"),
        track_id=None if track_id is None else bounded_int(track_id, "people.track_id"),
        zone=None if zone is None else required_str(zone, "people.zone"),
        display_name=None if display_name is None else required_str(display_name, "people.display_name"),
    )


def _event_payload(value: Any) -> EventPayload:
    if isinstance(value, EventPayload):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("events entries must be EventPayload or mappings")
    return EventPayload(
        event=required_str(value.get("event"), "events.event"),
        person_id=required_str(value.get("person_id"), "events.person_id"),
        timestamp=finite_float(value.get("timestamp"), "events.timestamp"),
        metadata=json_metadata(value.get("metadata")),
        schema_version=required_str(value.get("schema_version", EVENT_SCHEMA_VERSION), "events.schema_version"),
    )


def _sequence(value: object, field: str) -> tuple[object, ...]:
    if not isinstance(value, (tuple, list)):
        raise ValueError(f"{field} must be a sequence")
    return tuple(value)


def _counts(value: Any) -> Mapping[str, int]:
    if not isinstance(value, Mapping) or any(
        not isinstance(key, str) or not isinstance(count, int) for key, count in value.items()
    ):
        raise ValueError("counts must map event names to integer totals")
    return MappingProxyType(dict(value))


def snapshot_to_response(snapshot: Mapping[str, object]) -> ResponseSnapshot:
    updated_at = snapshot["updated_at"]
    age_seconds = snapshot["age_seconds"]
    error = snapshot["error"]
    persistence_data = snapshot.get("persistence")
    return ResponseSnapshot(
        status=required_str(snapshot["status"], "status"),
        error=None if error is None else required_str(error, "error"),
        demo_zones=bool(snapshot["demo_zones"]),
        frame=bounded_int(snapshot["frame"], "frame"),
        updated_at=None if updated_at is None else finite_float(updated_at, "updated_at"),
        age_seconds=None if age_seconds is None else finite_float(age_seconds, "age_seconds"),
        people=tuple(_person_payload(person) for person in _sequence(snapshot["people"], "people")),
        events=tuple(_event_payload(event) for event in _sequence(snapshot["events"], "events")),
        counts=_counts(snapshot["counts"]),
        processing_ms=finite_float(snapshot["processing_ms"], "processing_ms"),
        fps=finite_float(snapshot["fps"], "fps"),
        dropped_frames=bounded_int(snapshot["dropped_frames"], "dropped_frames"),
        persistence=None if persistence_data is None else json_metadata(persistence_data, "persistence"),
    )


def frame_to_response(jpeg: bytes | None, sequence: int) -> ResponseFrame:
    return ResponseFrame(jpeg=jpeg, sequence=sequence)
