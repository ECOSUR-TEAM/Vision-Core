import json
from dataclasses import MISSING, FrozenInstanceError, asdict, fields, is_dataclass
from typing import get_type_hints

import pytest

from vision_core.features.detection.application.dto.request.request_detector import RequestDetector
from vision_core.features.detection.application.dto.response.response_detector import ResponseDetector
from vision_core.features.detection.application.mappers.detection_mapper import (
    detection_to_dto,
    detections_to_response,
    response_to_detections,
)
from vision_core.features.detection.domain.entities.detection import Detection
from vision_core.shared.domain.bbox import BBox


def test_request_fields_and_types():
    request_fields = fields(RequestDetector)

    assert [field.name for field in request_fields] == ["frame"]
    assert get_type_hints(RequestDetector) == {"frame": object}
    assert all(field.default is MISSING and field.default_factory is MISSING for field in request_fields)


def test_response_fields_and_types():
    response_fields = fields(ResponseDetector)

    assert [field.name for field in response_fields] == ["detections"]
    assert get_type_hints(ResponseDetector) == {"detections": tuple[dict[str, object], ...]}
    assert all(field.default is MISSING and field.default_factory is MISSING for field in response_fields)


def test_dtos_are_immutable_and_slotted():
    for dto in (RequestDetector, ResponseDetector):
        assert is_dataclass(dto)
        assert dto.__dataclass_params__.frozen is True
        assert hasattr(dto, "__slots__")

    request = RequestDetector(frame=object())
    response = ResponseDetector(detections=())

    with pytest.raises(FrozenInstanceError):
        request.frame = object()
    with pytest.raises(FrozenInstanceError):
        response.detections = ()


def test_response_detections_are_json_serializable():
    response = ResponseDetector(
        detections=({"bbox": {"x1": 1, "y1": 2, "x2": 3, "y2": 4}, "class_id": 0, "confidence": 0.9, "track_id": 7},)
    )

    payload = json.loads(json.dumps(asdict(response), allow_nan=False))

    assert payload["detections"][0]["track_id"] == 7
    assert payload["detections"][0]["bbox"] == {"x1": 1, "y1": 2, "x2": 3, "y2": 4}


def test_detections_round_trip_through_response_dto():
    detection = Detection(BBox(1.0, 2.0, 11.0, 22.0), 0, 0.9, 7)

    response = ResponseDetector(detections=(detection_to_dto(detection),))

    assert response == detections_to_response([detection])
    assert response_to_detections(response) == [detection]
