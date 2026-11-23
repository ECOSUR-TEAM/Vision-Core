import json
from collections.abc import Mapping
from dataclasses import MISSING, FrozenInstanceError, fields, is_dataclass
from typing import get_type_hints

import numpy as np
import pytest

from tests.fakes.fake_detector import FakeDetector
from tests.fakes.fake_door import FakeDoor
from tests.fakes.fake_reid import FakeReID
from tests.fakes.fake_video_source import FakeVideoSource
from vision_core.core.domain.bbox import BBox
from vision_core.core.domain.event import Event
from vision_core.core.domain.event_type import EventType
from vision_core.core.dto import BBoxPayload, FrameLike, JSONValue, ResolvedTrackPayload
from vision_core.core.serialization import EVENT_SCHEMA_VERSION, dumps_json
from vision_core.core.serialization.events import event_to_dto, event_to_json
from vision_core.features.pipeline.application.dto.request.request_process_frame import RequestProcessFrame
from vision_core.features.pipeline.application.dto.request.request_run_pipeline import RequestRunPipeline
from vision_core.features.pipeline.application.dto.response.response_pipeline_event import ResponsePipelineEvent
from vision_core.features.pipeline.application.dto.response.response_process_frame import ResponseProcessFrame
from vision_core.features.pipeline.application.mappers.pipeline_mapper import resolved_track_to_dto
from vision_core.features.pipeline.application.use_cases.run_pipeline import RunPipeline
from vision_core.features.pipeline.domain.entities.resolved_track import ResolvedTrack

DTO_CLASSES = (
    RequestProcessFrame,
    RequestRunPipeline,
    ResponsePipelineEvent,
    ResponseProcessFrame,
)


def _metadata_hint(value: Mapping[str, JSONValue]) -> None:
    return None


def _response_event(event: Event) -> ResponsePipelineEvent:
    payload = event_to_dto(event)
    return ResponsePipelineEvent(
        event=payload.event,
        person_id=payload.person_id,
        timestamp=payload.timestamp,
        metadata=payload.metadata,
        schema_version=payload.schema_version,
    )


def test_request_fields_and_types():
    assert [field.name for field in fields(RequestProcessFrame)] == ["frame"]
    assert get_type_hints(RequestProcessFrame) == {"frame": FrameLike}
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
        "schema_version",
    ]
    assert get_type_hints(ResponsePipelineEvent) == {
        "event": str,
        "person_id": str,
        "timestamp": float,
        "metadata": get_type_hints(_metadata_hint)["value"],
        "schema_version": str,
    }

    assert [field.name for field in fields(ResponseProcessFrame)] == ["people", "events", "processing_ms"]
    assert get_type_hints(ResponseProcessFrame) == {
        "people": tuple[ResolvedTrackPayload, ...],
        "events": tuple[ResponsePipelineEvent, ...],
        "processing_ms": float,
    }

    required_fields = [field for field in fields(ResponsePipelineEvent) if field.name != "schema_version"]
    assert all(field.default is MISSING and field.default_factory is MISSING for field in required_fields)
    version_field = fields(ResponsePipelineEvent)[-1]
    assert version_field.name == "schema_version"
    assert version_field.default == EVENT_SCHEMA_VERSION
    assert all(field.default is MISSING and field.default_factory is MISSING for field in fields(ResponseProcessFrame))


def test_dtos_are_immutable_and_slotted():
    for dto in DTO_CLASSES:
        assert is_dataclass(dto)
        assert dto.__dataclass_params__.frozen is True
        assert hasattr(dto, "__slots__")

    instances = (
        (RequestProcessFrame(frame=np.zeros((1, 1, 3), dtype=np.uint8)), "frame"),
        (RequestRunPipeline(expected_frame_size=(640, 480)), "expected_frame_size"),
        (ResponsePipelineEvent(event="PERSON_ENTERED", person_id="person-1", timestamp=12.5, metadata={}), "metadata"),
        (ResponseProcessFrame(people=(), events=(), processing_ms=1.25), "processing_ms"),
    )
    for dto, field in instances:
        with pytest.raises(FrozenInstanceError):
            setattr(dto, field, None)


def test_request_dto_is_serializable():
    request = RequestRunPipeline(expected_frame_size=(640, 480))

    payload = json.loads(dumps_json(request))

    assert payload == {"expected_frame_size": [640, 480]}


def test_response_pipeline_event_is_serializable():
    event = Event(EventType.PERSON_ENTERED, "person-1", timestamp=12.5, metadata={"zone": "interior"})

    payload = dumps_json(event_to_dto(event))

    assert json.loads(payload) == {
        "event": "PERSON_ENTERED",
        "person_id": "person-1",
        "timestamp": 12.5,
        "metadata": {"zone": "interior"},
        "schema_version": EVENT_SCHEMA_VERSION,
    }
    assert json.loads(event_to_json(event))["metadata"] == {"zone": "interior"}


def test_response_process_frame_contains_people_and_processing_metrics():
    track = ResolvedTrack("person-1", BBox(1, 2, 3, 4), 0.9, 7)
    event = Event(EventType.PERSON_ENTERED, "person-1", timestamp=12.5, metadata={"zone": "interior"})
    response = ResponseProcessFrame(
        people=(resolved_track_to_dto(track),),
        events=(_response_event(event),),
        processing_ms=1.25,
    )

    payload = json.loads(dumps_json(response))

    assert payload["people"][0]["person_id"] == "person-1"
    assert payload["people"][0]["track_id"] == 7
    assert payload["people"][0]["bbox"] == {"x1": 1, "y1": 2, "x2": 3, "y2": 4}
    assert payload["events"] == [
        {
            "event": "PERSON_ENTERED",
            "person_id": "person-1",
            "timestamp": 12.5,
            "metadata": {"zone": "interior"},
            "schema_version": EVENT_SCHEMA_VERSION,
        }
    ]
    assert payload["processing_ms"] == 1.25


def test_nested_payloads_are_immutable():
    payload = ResolvedTrackPayload("person-1", BBoxPayload(1, 2, 3, 4), 0.9, 7)

    with pytest.raises(FrozenInstanceError):
        payload.track_id = 8


def test_event_metadata_is_immutable():
    event = Event(EventType.PERSON_ENTERED, "person-1", timestamp=12.5, metadata={"zone": {"name": "interior"}})

    response = _response_event(event)

    with pytest.raises(TypeError):
        response.metadata["zone"] = "exterior"
    with pytest.raises(TypeError):
        response.metadata["zone"]["name"] = "exterior"


def test_run_pipeline_adapter_preserves_serialized_event_fields():
    recorded: list[Event] = []
    frame = np.zeros((20, 20, 3), dtype=np.uint8)
    pipeline = RunPipeline(
        video=FakeVideoSource([frame]),
        detector=FakeDetector(),
        reid=FakeReID(),
        door=FakeDoor(),
        embedder=lambda crop: np.zeros(4),
        on_event=recorded.append,
    )

    response = pipeline.process_frame(RequestProcessFrame(frame))
    event = response.events[0]
    payload = event_to_dto(recorded[0])

    assert event == ResponsePipelineEvent(
        event=payload.event,
        person_id=payload.person_id,
        timestamp=payload.timestamp,
        metadata=payload.metadata,
        schema_version=payload.schema_version,
    )
    assert event.schema_version == EVENT_SCHEMA_VERSION
