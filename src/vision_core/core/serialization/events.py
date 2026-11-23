"""Serialización canónica de eventos de dominio a payloads versionados y JSON."""

from vision_core.core.domain.event import Event
from vision_core.core.dto.event_payload import EventPayload
from vision_core.core.serialization.json_value import JSONValue
from vision_core.core.serialization.serialization import dumps_json, to_json_value


def event_to_payload(event: Event) -> EventPayload:
    from vision_core.core.validation import finite_float, json_metadata, required_str

    return EventPayload(
        event=required_str(event.event, "event"),
        person_id=required_str(event.person_id, "person_id"),
        timestamp=finite_float(event.timestamp, "timestamp"),
        metadata=json_metadata(event.metadata),
    )


def event_to_dto(event: Event) -> EventPayload:
    return event_to_payload(event)


def event_to_json_dict(event: Event) -> dict[str, JSONValue]:
    payload = to_json_value(event_to_dto(event))
    if not isinstance(payload, dict):
        raise ValueError("Event DTO must serialize to a JSON object")
    return payload


def event_to_json(event: Event) -> str:
    try:
        return dumps_json(event_to_dto(event))
    except ValueError as exc:
        raise ValueError(f"Cannot serialize event {event.event!r} as JSON: {exc}") from exc
