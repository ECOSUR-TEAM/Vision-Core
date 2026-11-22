"""Mappers between door domain entities and transport payloads."""

from vision_core.core.domain.event import Event
from vision_core.core.dto.event_payload import EventPayload
from vision_core.core.dto.observation_payload import ObservationPayload
from vision_core.core.validation import finite_float, json_metadata, required_str
from vision_core.features.door.domain.entities.zone_observation import ZoneObservation


def event_to_dto(event: Event | None) -> EventPayload | None:
    if event is None:
        return None
    return EventPayload(
        event=required_str(event.event, "event"),
        person_id=required_str(event.person_id, "person_id"),
        timestamp=finite_float(event.timestamp, "timestamp"),
        metadata=json_metadata(event.metadata),
    )


def observation_to_dto(observation: ZoneObservation) -> ObservationPayload:
    position = observation.position
    if not isinstance(position, (tuple, list)) or len(position) != 2:
        raise ValueError("position must have exactly two coordinates")
    return ObservationPayload(
        position=(finite_float(position[0], "position.x"), finite_float(position[1], "position.y")),
        zone=required_str(observation.zone, "zone"),
        timestamp=finite_float(observation.timestamp, "timestamp"),
    )


def observations_to_dto(
    observations: tuple[ZoneObservation, ...],
) -> tuple[ObservationPayload, ...]:
    return tuple(observation_to_dto(observation) for observation in observations)
