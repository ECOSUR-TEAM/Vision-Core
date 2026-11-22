import json
from collections.abc import Mapping
from dataclasses import MISSING, FrozenInstanceError, fields, is_dataclass
from typing import cast, get_type_hints

import pytest

from vision_core.core.dto import BBoxPayload, EventPayload, JSONValue, MonitorPersonPayload
from vision_core.core.serialization import dumps_json
from vision_core.features.monitor.application.dto.request.request_frame import RequestFrame
from vision_core.features.monitor.application.dto.request.request_snapshot import RequestSnapshot
from vision_core.features.monitor.application.dto.response.response_frame import ResponseFrame
from vision_core.features.monitor.application.dto.response.response_snapshot import ResponseSnapshot
from vision_core.features.monitor.application.mappers.monitor_mapper import snapshot_to_response

DTO_CLASSES = (RequestFrame, RequestSnapshot, ResponseFrame, ResponseSnapshot)


def _persistence_hint() -> Mapping[str, JSONValue] | None:
    raise NotImplementedError


PERSON = MonitorPersonPayload(
    person_id="person-1",
    bbox=BBoxPayload(1, 2, 3, 4),
    confidence=0.9,
    track_id=7,
    zone="interior",
    display_name="Persona 1",
)


def test_request_fields_and_types():
    after = fields(RequestFrame)[0]

    assert [field.name for field in fields(RequestFrame)] == ["after"]
    assert get_type_hints(RequestFrame) == {"after": int | None}
    assert after.default is None and after.default_factory is MISSING
    assert [field.name for field in fields(RequestSnapshot)] == []
    assert get_type_hints(RequestSnapshot) == {}


def test_response_fields_and_types():
    assert [field.name for field in fields(ResponseFrame)] == ["jpeg", "sequence"]
    assert get_type_hints(ResponseFrame) == {"jpeg": bytes | None, "sequence": int}

    assert [field.name for field in fields(ResponseSnapshot)] == [
        "status",
        "error",
        "demo_zones",
        "frame",
        "updated_at",
        "age_seconds",
        "people",
        "events",
        "counts",
        "processing_ms",
        "fps",
        "dropped_frames",
        "persistence",
    ]
    hints = get_type_hints(ResponseSnapshot)
    assert hints["persistence"] == get_type_hints(_persistence_hint)["return"]
    assert {key: value for key, value in hints.items() if key != "persistence"} == {
        "status": str,
        "error": str | None,
        "demo_zones": bool,
        "frame": int,
        "updated_at": float | None,
        "age_seconds": float | None,
        "people": tuple[MonitorPersonPayload, ...],
        "events": tuple[EventPayload, ...],
        "counts": Mapping[str, int],
        "processing_ms": float,
        "fps": float,
        "dropped_frames": int,
    }

    for dto in (ResponseFrame, ResponseSnapshot):
        assert all(field.default is MISSING and field.default_factory is MISSING for field in fields(dto))


def test_dtos_are_immutable_and_slotted():
    for dto in DTO_CLASSES:
        assert is_dataclass(dto)
        assert dto.__dataclass_params__.frozen is True
        assert hasattr(dto, "__slots__")

    instances = (
        (RequestFrame(), "after"),
        (
            ResponseSnapshot(
                status="running",
                error=None,
                demo_zones=False,
                frame=4,
                updated_at=10.0,
                age_seconds=0.1,
                people=(),
                events=(),
                counts={},
                processing_ms=2.0,
                fps=15.0,
                dropped_frames=0,
                persistence=None,
            ),
            "status",
        ),
        (ResponseFrame(b"jpeg", 4), "jpeg"),
    )
    for dto, field in instances:
        with pytest.raises(FrozenInstanceError):
            setattr(dto, field, None)


def test_snapshot_response_is_json_serializable():
    response = ResponseSnapshot(
        status="running",
        error=None,
        demo_zones=False,
        frame=4,
        updated_at=10.0,
        age_seconds=0.1,
        people=(PERSON,),
        events=(EventPayload("PERSON_ENTERED", "person-1", 10.0, {"zone": "interior"}),),
        counts={"interior": 1},
        processing_ms=2.0,
        fps=15.0,
        dropped_frames=0,
        persistence=None,
    )

    payload = json.loads(dumps_json(response))

    assert payload["status"] == "running"
    assert payload["counts"] == {"interior": 1}
    assert payload["people"] == [
        {
            "person_id": "person-1",
            "bbox": {"x1": 1, "y1": 2, "x2": 3, "y2": 4},
            "confidence": 0.9,
            "track_id": 7,
            "zone": "interior",
            "display_name": "Persona 1",
        }
    ]


def test_frame_response_serializes_binary_payload_as_null():
    response = ResponseFrame(jpeg=b"jpeg", sequence=4)

    payload = json.loads(dumps_json(response))

    assert payload == {"jpeg": None, "sequence": 4}
    assert response.jpeg == b"jpeg"


def test_nested_mappings_are_immutable():
    response = snapshot_to_response(
        {
            "status": "running",
            "error": None,
            "demo_zones": False,
            "frame": 4,
            "updated_at": 10.0,
            "age_seconds": 0.1,
            "people": (),
            "events": (
                {
                    "event": "PERSON_ENTERED",
                    "person_id": "person-1",
                    "timestamp": 10.0,
                    "metadata": {"zone": {"name": "interior"}},
                },
            ),
            "counts": {"interior": 1},
            "processing_ms": 2.0,
            "fps": 15.0,
            "dropped_frames": 0,
            "persistence": {"enabled": True, "health": {"ready": True}},
        }
    )

    with pytest.raises(TypeError):
        response.counts["interior"] = 5
    with pytest.raises(TypeError):
        response.events[0].metadata["zone"] = "exterior"
    with pytest.raises(TypeError):
        response.events[0].metadata["zone"]["name"] = "exterior"
    assert response.persistence is not None
    persistence_health = cast("Mapping[str, JSONValue]", response.persistence["health"])
    with pytest.raises(TypeError):
        persistence_health["ready"] = False
