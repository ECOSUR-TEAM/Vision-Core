import json
from dataclasses import MISSING, FrozenInstanceError, fields, is_dataclass
from typing import get_type_hints

import numpy as np
import pytest

from vision_core.features.detection.application.dto.request.request_detector import RequestDetector
from vision_core.features.detection.application.dto.response.response_detector import ResponseDetector
from vision_core.features.detection.application.mappers.detection_mapper import (
    detection_to_dto,
    detections_to_response,
    response_to_detections,
)
from vision_core.features.detection.domain.entities.detection import Detection
from vision_core.shared.application.dto import BBoxPayload, DetectionPayload, FrameLike
from vision_core.shared.application.dto.serialization import dumps_json
from vision_core.shared.application.validation import finite_bbox
from vision_core.shared.domain.bbox import BBox


def test_request_fields_and_types():
    request_fields = fields(RequestDetector)

    assert [field.name for field in request_fields] == ["frame"]
    assert get_type_hints(RequestDetector) == {"frame": FrameLike}
    assert all(field.default is MISSING and field.default_factory is MISSING for field in request_fields)


def test_response_fields_and_types():
    response_fields = fields(ResponseDetector)

    assert [field.name for field in response_fields] == ["detections"]
    assert get_type_hints(ResponseDetector) == {"detections": tuple[DetectionPayload, ...]}
    assert all(field.default is MISSING and field.default_factory is MISSING for field in response_fields)


def test_dtos_are_immutable_and_slotted():
    for dto in (RequestDetector, ResponseDetector):
        assert is_dataclass(dto)
        assert dto.__dataclass_params__.frozen is True
        assert hasattr(dto, "__slots__")

    request = RequestDetector(frame=np.zeros((1, 1, 3), dtype=np.uint8))
    response = ResponseDetector(detections=())

    with pytest.raises(FrozenInstanceError):
        request.frame = object()
    with pytest.raises(FrozenInstanceError):
        response.detections = ()


def test_response_detections_are_json_serializable():
    response = ResponseDetector(
        detections=(DetectionPayload(BBoxPayload(1, 2, 3, 4), class_id=0, confidence=0.9, track_id=7),)
    )

    payload = json.loads(dumps_json(response))

    assert payload["detections"][0]["track_id"] == 7
    assert payload["detections"][0]["bbox"] == {"x1": 1, "y1": 2, "x2": 3, "y2": 4}


def test_detections_round_trip_through_response_dto():
    detection = Detection(BBox(1.0, 2.0, 11.0, 22.0), 0, 0.9, 7)

    response = ResponseDetector(detections=(detection_to_dto(detection),))

    assert response == detections_to_response([detection])
    assert response_to_detections(response) == [detection]


def test_detection_mapper_validates_at_the_boundary():
    invalid_area = DetectionPayload(BBoxPayload(2, 2, 1, 1), class_id=0, confidence=0.9, track_id=7)
    invalid_confidence = DetectionPayload(BBoxPayload(1, 2, 3, 4), class_id=0, confidence=float("nan"), track_id=7)
    missing_track = DetectionPayload(BBoxPayload(1, 2, 3, 4), class_id=0, confidence=0.9, track_id=None)

    with pytest.raises(ValueError, match="bbox must have positive area"):
        response_to_detections(ResponseDetector(detections=(invalid_area,)))
    with pytest.raises(ValueError, match="confidence must be a finite number"):
        response_to_detections(ResponseDetector(detections=(invalid_confidence,)))
    with pytest.raises(ValueError, match="track_id is required at the DTO boundary"):
        response_to_detections(ResponseDetector(detections=(missing_track,)))


@pytest.mark.parametrize("coordinate", [float("nan"), float("inf"), float("-inf")])
def test_finite_bbox_rejects_non_finite_bbox_payload(coordinate):
    with pytest.raises(ValueError, match="bbox.x1 must be a finite number"):
        finite_bbox(BBoxPayload(coordinate, 0, 2, 1))
