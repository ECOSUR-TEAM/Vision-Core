import sys
from types import SimpleNamespace

import numpy as np
import pytest

from tests.fakes.fake_detector import FakeDetector
from vision_core.features.detection.domain.entities.detection import Detection
from vision_core.features.detection.domain.ports.detector_manager import DetectorManager
from vision_core.features.detection.infrastructure.adapters.yolo_detector_manager import YoloDetectorManager
from vision_core.shared.errors import ValidationError, codes

FRAME = np.zeros((40, 80, 3), dtype=np.uint8)


def _yolo_detector(monkeypatch):
    box = SimpleNamespace(
        xyxy=np.array([[1, 2, 21, 42]]),
        conf=np.array([0.9]),
        cls=np.array([0]),
    )
    model = SimpleNamespace(boxes=[box])
    model.predict = lambda frame, **kwargs: [SimpleNamespace(boxes=model.boxes)]
    monkeypatch.setitem(sys.modules, "ultralytics", SimpleNamespace(YOLO=lambda path: model))
    return YoloDetectorManager()


def _assert_detector_contract(detector):
    assert isinstance(detector, DetectorManager)
    detections = detector.process(FRAME)
    assert isinstance(detections, list)
    assert all(isinstance(detection, Detection) for detection in detections)
    assert all(isinstance(detection.track_id, int) for detection in detections)
    assert isinstance(detector.pop_lost_track_ids(), list)


def test_fake_detector_honours_port_contract():
    _assert_detector_contract(FakeDetector())


def test_real_detector_honours_port_contract_with_injected_model(monkeypatch):
    _assert_detector_contract(_yolo_detector(monkeypatch))


def test_real_detector_rejects_invalid_frame_with_stable_code(monkeypatch):
    with pytest.raises(ValidationError) as error:
        _yolo_detector(monkeypatch).process(np.zeros((4, 4), dtype=np.uint8))
    assert error.value.code == codes.MODEL_INPUT_INVALID
