from vision_core.features.door.application.mappers.door_mapper import (
    event_to_dto,
    observation_to_dto,
    observations_to_dto,
)
from vision_core.features.door.domain.entities.zone_observation import ZoneObservation
from vision_core.shared.domain.event import Event


def test_event_to_dto_handles_missing_event():
    assert event_to_dto(None) is None


def test_event_to_dto_copies_public_event_fields():
    event = Event("PERSON_ENTERED", "person-1", timestamp=10.0, metadata={"zone": "interior"})

    payload = event_to_dto(event)

    assert payload == {
        "event": "PERSON_ENTERED",
        "person_id": "person-1",
        "timestamp": 10.0,
        "metadata": {"zone": "interior"},
    }
    event.metadata["zone"] = "exterior"
    assert payload["metadata"] == {"zone": "interior"}


def test_observation_and_collection_mappers_preserve_domain_data():
    observation = ZoneObservation((1.0, 2.0), "exterior", 10.0)

    assert observation_to_dto(observation) == {"position": (1.0, 2.0), "zone": "exterior", "timestamp": 10.0}
    assert observations_to_dto((observation,)) == (observation_to_dto(observation),)
