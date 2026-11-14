import sys
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from infrastructure.detection.yolo_detector_manager import (
    KEYPOINT_CONFIDENCE,
    MIN_VISIBLE_KEYPOINTS,
    PosePersonDetectorManager,
    YoloDetectorManager,
    person_detector_from_env,
)


def box(x, confidence=0.9, class_id=0):
    return SimpleNamespace(
        xyxy=np.array([[x, 20, x + 20, 60]]),
        conf=np.array([confidence]),
        cls=np.array([class_id]),
    )


def pose_result(boxes, keypoint_confidences):
    return SimpleNamespace(
        boxes=boxes,
        keypoints=SimpleNamespace(conf=np.array(keypoint_confidences, dtype=float)),
        orig_shape=(80, 160),
    )


@pytest.fixture
def detector(monkeypatch):
    model = SimpleNamespace(result=None)
    model.predict = lambda frame, **kwargs: [model.result]
    monkeypatch.setitem(sys.modules, "ultralytics", SimpleNamespace(YOLO=lambda path: model))
    manager = PosePersonDetectorManager()

    def process(boxes, keypoint_confidences):
        model.result = pose_result(boxes, keypoint_confidences)
        return manager.process(np.zeros((80, 160, 3), dtype=np.uint8))

    process.manager = manager
    process.model = model
    return process


def test_accepts_person_with_enough_visible_keypoints(detector):
    keypoints = [0.1] * 17
    for index in (5, 6, 11, 12):
        keypoints[index] = 0.9
    detections = detector([box(40, 0.9)], [keypoints])
    assert len(detections) == 1
    assert detections[0].class_id == 0
    assert detections[0].confidence == 0.9


def test_rejects_plush_like_object_without_visible_keypoints(detector):
    # Measured on the plush: box confidence 0.75 but every keypoint <= 0.28.
    keypoints = [0.04, 0.02, 0.01, 0.07, 0.02, 0.19, 0.28, 0.09, 0.13,
                 0.08, 0.07, 0.03, 0.03, 0.01, 0.01, 0.01, 0.0]
    assert detector([box(40, 0.75)], [keypoints]) == []


def test_rejects_when_keypoints_are_missing(detector):
    detector.model.result = SimpleNamespace(boxes=[box(40, 0.9)], keypoints=None)
    assert detector.manager.process(np.zeros((80, 160, 3), dtype=np.uint8)) == []


def test_keypoint_threshold_boundary(detector):
    enough = [0.0] * 17
    for index in (5, 6, 11, 12):
        enough[index] = KEYPOINT_CONFIDENCE
    assert len(detector([box(40)], [enough])) == 1
    below = [0.0] * 17
    for index in (5, 6, 11, 12):
        below[index] = KEYPOINT_CONFIDENCE - 0.01
    assert detector([box(40)], [below]) == []


def test_rejects_upper_body_only_false_positive(detector):
    # The plush produced a plausible upper-body skeleton (7 keypoints >= 0.5)
    # but no visible hips, so the hip check must reject it.
    keypoints = [0.83, 0.69, 0.6, 0.46, 0.23, 0.85, 0.9, 0.63, 0.67,
                 0.44, 0.47, 0.27, 0.31, 0.02, 0.03, 0.01, 0.01]
    assert detector([box(40, 0.76)], [keypoints]) == []


def test_accepts_truncated_person_without_visible_hips(detector):
    # Real person cut off at the right edge: hips are out of frame (0.0)
    # but upper-body keypoints are visible and the box touches the edge.
    keypoints = [0.98, 0.96, 0.99, 0.54, 0.95, 0.83, 0.95, 0.03, 0.13,
                 0.02, 0.06, 0.0, 0.01, 0.0, 0.0, 0.0, 0.0]
    edge_box = SimpleNamespace(
        xyxy=np.array([[120, 20, 160, 79]]),
        conf=np.array([0.93]),
        cls=np.array([0]),
    )
    assert len(detector([edge_box], [keypoints])) == 1


def test_pose_detector_tracks_accepted_people(detector):
    keypoints = [0.9] * 17
    first = detector([box(40)], [keypoints])[0]
    second = detector([box(45)], [keypoints])[0]
    assert second.track_id == first.track_id


def test_pose_detector_loads_default_model_and_predict_settings(monkeypatch):
    model = Mock()
    model.predict.return_value = [pose_result([], [])]
    loader = Mock(return_value=model)
    monkeypatch.setitem(sys.modules, "ultralytics", SimpleNamespace(YOLO=loader))
    manager = PosePersonDetectorManager()
    manager.process(np.zeros((48, 64, 3), dtype=np.uint8))
    loader.assert_called_once_with("yolov8n-pose.pt")
    assert model.predict.call_args.kwargs == dict(verbose=False, classes=[0], conf=0.5)


def test_person_detector_from_env_defaults_to_pose(monkeypatch):
    loader = Mock(return_value=SimpleNamespace())
    monkeypatch.setitem(sys.modules, "ultralytics", SimpleNamespace(YOLO=loader))
    monkeypatch.delenv("VISION_CORE_PERSON_DETECTOR", raising=False)
    monkeypatch.delenv("VISION_CORE_YOLO_MODEL", raising=False)
    detector = person_detector_from_env()
    assert isinstance(detector, PosePersonDetectorManager)
    loader.assert_called_once_with("yolov8n-pose.pt")


def test_person_detector_from_env_can_select_detection(monkeypatch):
    loader = Mock(return_value=SimpleNamespace())
    monkeypatch.setitem(sys.modules, "ultralytics", SimpleNamespace(YOLO=loader))
    monkeypatch.setenv("VISION_CORE_PERSON_DETECTOR", "detect")
    monkeypatch.delenv("VISION_CORE_YOLO_MODEL", raising=False)
    detector = person_detector_from_env()
    assert isinstance(detector, YoloDetectorManager)
    assert not isinstance(detector, PosePersonDetectorManager)
    loader.assert_called_once_with("yolov8n.pt")


def test_person_detector_from_env_rejects_unknown_kind(monkeypatch):
    monkeypatch.setenv("VISION_CORE_PERSON_DETECTOR", "other")
    with pytest.raises(ValueError, match="pose.*detect"):
        person_detector_from_env()
