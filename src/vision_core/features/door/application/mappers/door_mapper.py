from vision_core.features.door.domain.entities.zone_observation import ZoneObservation
from vision_core.shared.domain.event import Event


def event_to_dto(event: Event | None) -> dict[str, object] | None:
    if event is None:
        return None
    return {
        "event": event.event,
        "person_id": event.person_id,
        "timestamp": event.timestamp,
        "metadata": dict(event.metadata),
    }


def observation_to_dto(observation: ZoneObservation) -> dict[str, object]:
    return {
        "position": observation.position,
        "zone": observation.zone,
        "timestamp": observation.timestamp,
    }


def observations_to_dto(
    observations: tuple[ZoneObservation, ...],
) -> tuple[dict[str, object], ...]:
    return tuple(observation_to_dto(observation) for observation in observations)
