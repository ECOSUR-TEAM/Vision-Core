import json
from dataclasses import MISSING, FrozenInstanceError, asdict, fields, is_dataclass, replace
from typing import get_type_hints

import pytest

from vision_core.features.monitor.application.dto.request.request_frame import RequestFrame
from vision_core.features.monitor.application.dto.request.request_snapshot import RequestSnapshot
from vision_core.features.monitor.application.dto.response.response_frame import ResponseFrame
from vision_core.features.monitor.application.dto.response.response_snapshot import ResponseSnapshot

DTO_CLASSES = (RequestFrame, RequestSnapshot, ResponseFrame, ResponseSnapshot)


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
    ]
    assert get_type_hints(ResponseSnapshot) == {
        "status": str,
        "error": str | None,
        "demo_zones": bool,
        "frame": int,
        "updated_at": float | None,
        "age_seconds": float | None,
        "people": tuple[dict[str, object], ...],
        "events": tuple[dict[str, object], ...],
        "counts": dict[str, int],
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
        people=({"person_id": "person-1"},),
        events=(),
        counts={"interior": 1},
        processing_ms=2.0,
        fps=15.0,
        dropped_frames=0,
    )

    payload = json.loads(json.dumps(asdict(response), allow_nan=False))

    assert payload["status"] == "running"
    assert payload["counts"] == {"interior": 1}
    assert payload["people"] == [{"person_id": "person-1"}]


def test_frame_response_serializes_without_binary_payload():
    response = replace(ResponseFrame(jpeg=b"jpeg", sequence=4), jpeg=None)

    payload = json.loads(json.dumps(asdict(response), allow_nan=False))

    assert payload == {"jpeg": None, "sequence": 4}
