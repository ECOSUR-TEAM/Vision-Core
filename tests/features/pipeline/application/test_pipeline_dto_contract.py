import json
from dataclasses import MISSING, FrozenInstanceError, asdict, fields, is_dataclass
from typing import Any, get_type_hints

import pytest

from vision_core.features.pipeline.application.dto.request.request_process_frame import RequestProcessFrame
from vision_core.features.pipeline.application.dto.request.request_run_pipeline import RequestRunPipeline
from vision_core.features.pipeline.application.dto.response.response_pipeline_event import ResponsePipelineEvent
from vision_core.features.pipeline.application.dto.response.response_process_frame import ResponseProcessFrame
from vision_core.features.pipeline.application.mappers.pipeline_mapper import (
    event_to_dict,
    event_to_dto,
    resolved_track_to_dto,
)
from vision_core.features.pipeline.domain.entities.resolved_track import ResolvedTrack
from vision_core.shared.domain.bbox import BBox
from vision_core.shared.domain.event import Event
from vision_core.shared.domain.event_type import EventType

DTO_CLASSES = (
    RequestProcessFrame,
    RequestRunPipeline,
    ResponsePipelineEvent,
    ResponseProcessFrame,
)


def test_request_fields_and_types():
    assert [field.name for field in fields(RequestProcessFrame)] == ["frame"]
    assert get_type_hints(RequestProcessFrame) == {"frame": object}
    assert all(field.default is MISSING and field.default_factory is MISSING for field in fields(RequestProcessFrame))

    expected_size = fields(RequestRunPipeline)[0]
    assert [field.name for field in fields(RequestRunPipeline)] == ["expected_frame_size"]
    assert get_type_hints(RequestRunPipeline) == {"expected_frame_size": tuple[int, int] | None}
    assert expected_size.default is None and expected_size.default_factory is MISSING


def test_response_fields_and_types():
    assert [field.name for field in fields(ResponsePipelineEvent)] == [
        "event",
        "person_id",
        "timestamp",
        "metadata",
    ]
    assert get_type_hints(ResponsePipelineEvent) == {
        "event": str,
        "person_id": str,
        "timestamp": float,
        "metadata": dict[str, Any],
    }

    assert [field.name for field in fields(ResponseProcessFrame)] == ["people", "events", "processing_ms"]
    assert get_type_hints(ResponseProcessFrame) == {
        "people": tuple[dict[str, Any], ...],
        "events": tuple[dict[str, Any], ...],
        "processing_ms": float,
    }

    for dto in (ResponsePipelineEvent, ResponseProcessFrame):
        assert all(field.default is MISSING and field.default_factory is MISSING for field in fields(dto))


def test_dtos_are_immutable_and_slotted():
    for dto in DTO_CLASSES:
        assert is_dataclass(dto)
        assert dto.__dataclass_params__.frozen is True
        assert hasattr(dto, "__slots__")

    instances = (
        (RequestProcessFrame(frame=object()), "frame"),
        (RequestRunPipeline(expected_frame_size=(640, 480)), "expected_frame_size"),
        (ResponsePipelineEvent(event="PERSON_ENTERED", person_id="person-1", timestamp=12.5, metadata={}), "metadata"),
        (ResponseProcessFrame(people=(), events=(), processing_ms=1.25), "processing_ms"),
    )
    for dto, field in instances:
        with pytest.raises(FrozenInstanceError):
            setattr(dto, field, None)


def test_request_dto_is_serializable():
    request = RequestRunPipeline(expected_frame_size=(640, 480))

    payload = json.loads(json.dumps(asdict(request), allow_nan=False))

    assert payload == {"expected_frame_size": [640, 480]}


def test_response_pipeline_event_is_serializable():
    event = Event(EventType.PERSON_ENTERED, "person-1", timestamp=12.5, metadata={"zone": "interior"})

    payload = asdict(event_to_dto(event))

    assert payload == {
        "event": "PERSON_ENTERED",
        "person_id": "person-1",
        "timestamp": 12.5,
        "metadata": {"zone": "interior"},
    }
    assert json.loads(json.dumps(payload, allow_nan=False)) == payload


def test_response_process_frame_contains_people_and_processing_metrics():
    track = ResolvedTrack("person-1", BBox(1, 2, 3, 4), 0.9, 7)
    event = Event(EventType.PERSON_ENTERED, "person-1", timestamp=12.5, metadata={"zone": "interior"})
    response = ResponseProcessFrame(
        people=(resolved_track_to_dto(track),),
        events=(event_to_dict(event),),
        processing_ms=1.25,
    )

    payload = json.loads(json.dumps(asdict(response), allow_nan=False))

    assert payload["people"][0]["person_id"] == "person-1"
    assert payload["people"][0]["track_id"] == 7
    assert payload["people"][0]["bbox"] == {"x1": 1, "y1": 2, "x2": 3, "y2": 4}
    assert payload["events"] == [
        {
            "event": "PERSON_ENTERED",
            "person_id": "person-1",
            "timestamp": 12.5,
            "metadata": {"zone": "interior"},
        }
    ]
    assert payload["processing_ms"] == 1.25
