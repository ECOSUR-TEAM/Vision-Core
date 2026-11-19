import json
from dataclasses import asdict

import pytest

from vision_core.features.pipeline.application.dto.request.request_run_pipeline import RequestRunPipeline
from vision_core.features.pipeline.application.dto.response.response_process_frame import ResponseProcessFrame
from vision_core.features.pipeline.application.mappers.pipeline_mapper import event_to_dto, resolved_track_to_dto
from vision_core.features.pipeline.domain.entities.resolved_track import ResolvedTrack
from vision_core.shared.domain.bbox import BBox
from vision_core.shared.domain.event import Event
from vision_core.shared.domain.event_type import EventType


def test_request_dto_is_immutable_and_serializable():
    request = RequestRunPipeline(expected_frame_size=(640, 480))

    assert asdict(request) == {"expected_frame_size": (640, 480)}
    with pytest.raises(Exception):
        request.expected_frame_size = None


def test_response_pipeline_event_is_serializable():
    event = Event(EventType.PERSON_ENTERED, "person-1", timestamp=12.5, metadata={"zone": "interior"})

    payload = asdict(event_to_dto(event))

    assert payload == {
        "event": "PERSON_ENTERED",
        "person_id": "person-1",
        "timestamp": 12.5,
        "metadata": {"zone": "interior"},
    }
    assert json.loads(json.dumps(payload)) == payload


def test_response_process_frame_contains_people_and_processing_metrics():
    track = ResolvedTrack("person-1", BBox(1, 2, 3, 4), 0.9, 7)
    response = ResponseProcessFrame(
        people=(resolved_track_to_dto(track),),
        events=(),
        processing_ms=1.25,
    )

    payload = json.loads(json.dumps(asdict(response)))

    assert payload["people"][0]["person_id"] == "person-1"
    assert payload["people"][0]["track_id"] == 7
    assert payload["people"][0]["bbox"] == {"x1": 1, "y1": 2, "x2": 3, "y2": 4}
    assert payload["events"] == []
    assert payload["processing_ms"] == 1.25
