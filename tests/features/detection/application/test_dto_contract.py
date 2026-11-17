from dataclasses import FrozenInstanceError

import pytest

from vision_core.features.detection.application.dto.request.request_detector import RequestDetector
from vision_core.features.detection.application.dto.response.response_detector import ResponseDetector


def test_request_and_response_dtos_are_immutable():
    request = RequestDetector(frame=object())
    response = ResponseDetector(detections=())

    with pytest.raises(FrozenInstanceError):
        request.frame = object()
    with pytest.raises(FrozenInstanceError):
        response.detections = ()
