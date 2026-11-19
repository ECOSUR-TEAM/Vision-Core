import json
from dataclasses import MISSING, FrozenInstanceError, asdict, fields, is_dataclass
from typing import get_type_hints

import pytest

from vision_core.features.door.application.dto.request.request_get_history import RequestGetHistory
from vision_core.features.door.application.dto.request.request_update import RequestUpdate
from vision_core.features.door.application.dto.response.response_get_history import ResponseGetHistory
from vision_core.features.door.application.dto.response.response_update import ResponseUpdate

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
    assert get_type_hints(ResponseGetHistory) == {"observations": tuple[dict[str, object], ...]}

    assert [field.name for field in fields(ResponseUpdate)] == ["event"]
    assert get_type_hints(ResponseUpdate) == {"event": dict[str, object] | None}

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
    update = ResponseUpdate(event={"event": "PERSON_ENTERED", "person_id": "person-1", "timestamp": 10.0})
    history = ResponseGetHistory(observations=({"position": (1.0, 2.0), "zone": "exterior", "timestamp": 10.0},))

    update_payload = json.loads(json.dumps(asdict(update), allow_nan=False))
    history_payload = json.loads(json.dumps(asdict(history), allow_nan=False))

    assert update_payload["event"]["person_id"] == "person-1"
    assert history_payload["observations"][0]["zone"] == "exterior"
