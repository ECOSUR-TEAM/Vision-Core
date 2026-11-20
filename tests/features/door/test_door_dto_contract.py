import json
from dataclasses import MISSING, FrozenInstanceError, fields, is_dataclass
from typing import get_type_hints

import pytest

from vision_core.features.door.application.dto.request.request_get_history import RequestGetHistory
from vision_core.features.door.application.dto.request.request_update import RequestUpdate
from vision_core.features.door.application.dto.response.response_get_history import ResponseGetHistory
from vision_core.features.door.application.dto.response.response_update import ResponseUpdate
from vision_core.features.door.application.mappers.door_mapper import event_to_dto
from vision_core.shared.application.dto import EventPayload, ObservationPayload
from vision_core.shared.application.dto.serialization import dumps_json
from vision_core.shared.domain.event import Event
from vision_core.shared.domain.event_type import EventType

DTO_CLASSES = (RequestGetHistory, RequestUpdate, ResponseGetHistory, ResponseUpdate)


def test_request_fields_and_types():
    assert [field.name for field in fields(RequestGetHistory)] == ["person_id"]
    assert get_type_hints(RequestGetHistory) == {"person_id": str}

    assert [field.name for field in fields(RequestUpdate)] == ["person_id", "position"]
    assert get_type_hints(RequestUpdate) == {"person_id": str, "position": tuple[float, float]}

    for dto in (RequestGetHistory, RequestUpdate):
        assert all(field.default is MISSING and field.default_factory is MISSING for field in fields(dto))


def test_response_fields_and_types():
    assert [field.name for field in fields(ResponseGetHistory)] == ["observations"]
    assert get_type_hints(ResponseGetHistory) == {"observations": tuple[ObservationPayload, ...]}

    assert [field.name for field in fields(ResponseUpdate)] == ["event"]
    assert get_type_hints(ResponseUpdate) == {"event": EventPayload | None}

    for dto in (ResponseGetHistory, ResponseUpdate):
        assert all(field.default is MISSING and field.default_factory is MISSING for field in fields(dto))


def test_dtos_are_immutable_and_slotted():
    for dto in DTO_CLASSES:
        assert is_dataclass(dto)
        assert dto.__dataclass_params__.frozen is True
        assert hasattr(dto, "__slots__")

    instances = (
        (RequestGetHistory("person-1"), "person_id"),
        (RequestUpdate("person-1", (1.0, 2.0)), "position"),
        (ResponseGetHistory(()), "observations"),
        (ResponseUpdate(None), "event"),
    )
    for dto, field in instances:
        with pytest.raises(FrozenInstanceError):
            setattr(dto, field, None)


def test_responses_are_json_serializable():
    update = ResponseUpdate(event=EventPayload("PERSON_ENTERED", "person-1", 10.0, {"zone": "interior"}))
    history = ResponseGetHistory(observations=(ObservationPayload((1.0, 2.0), "exterior", 10.0),))

    update_payload = json.loads(dumps_json(update))
    history_payload = json.loads(dumps_json(history))

    assert update_payload["event"]["person_id"] == "person-1"
    assert history_payload["observations"][0]["zone"] == "exterior"


def test_nested_payloads_are_immutable():
    observation = ObservationPayload((1.0, 2.0), "exterior", 10.0)

    with pytest.raises(FrozenInstanceError):
        observation.zone = "interior"


def test_event_metadata_is_immutable():
    event = Event(EventType.PERSON_ENTERED, "person-1", timestamp=10.0, metadata={"zone": {"name": "interior"}})

    payload = event_to_dto(event)

    with pytest.raises(TypeError):
        payload.metadata["zone"] = "exterior"
    with pytest.raises(TypeError):
        payload.metadata["zone"]["name"] = "exterior"
