import sys
from types import SimpleNamespace

import numpy as np
import pytest

from domain.entities import Detection
from infrastructure.detection.yolo_detector_manager import (
    MAX_MISSED_FRAMES,
    YoloDetectorManager,
)


def box(x, confidence=0.9, class_id=0):
    return SimpleNamespace(
        xyxy=np.array([[x, 0, x + 20, 40]]),
        conf=np.array([confidence]),
        cls=np.array([class_id]),
    )


@pytest.fixture
def detector(monkeypatch):
    model = SimpleNamespace(boxes=[])
    model.predict = lambda frame, **kwargs: [SimpleNamespace(boxes=model.boxes)]
    monkeypatch.setitem(sys.modules, "ultralytics", SimpleNamespace(YOLO=lambda path: model))
    manager = YoloDetectorManager()

    def process(boxes):
        model.boxes = boxes
        return manager.process(np.zeros((80, 160, 3), dtype=np.uint8))

    process.manager = manager
    return process


def test_filters_before_tracking_and_returns_domain_entities(detector):
    detections = detector([box(0, 0.5), box(30, class_id=2), box(60, 0.8)])
    assert len(detections) == 1
    detection = detections[0]
    assert isinstance(detection, Detection)
    assert detection.class_id == 0
    assert detection.confidence == 0.8
    assert detection.bbox.x1 == 60
    assert detection.track_id > 0


def test_ids_follow_people_through_crossing_and_reordered_boxes(detector):
    first, second = detector([box(0), box(60)])
    assert first.track_id != second.track_id
    for frame in range(1, 13):
        a, b = box(frame * 5), box(60 - frame * 5)
        reverse = frame % 2 == 1
        detections = detector([b, a] if reverse else [a, b])
        ids = [d.track_id for d in detections]
        expected = [first.track_id, second.track_id]
        if frame != 6:
            assert ids == (expected[::-1] if reverse else expected)
        assert len(set(ids)) == 2


def test_missing_detection_uses_motion_and_returns_no_phantom_boxes(detector):
    track_id = detector([box(0)])[0].track_id
    assert detector([box(5)])[0].track_id == track_id
    assert detector([]) == []
    assert detector([box(15)])[0].track_id == track_id


def test_filtered_frames_age_tracks_and_expired_ids_are_not_reused(detector):
    track_id = detector([box(0)])[0].track_id
    for _ in range(MAX_MISSED_FRAMES + 1):
        assert detector([box(0, 0.4)]) == []
    assert detector([box(0)])[0].track_id != track_id


def test_new_person_gets_distinct_id_without_changing_existing_id(detector):
    track_id = detector([box(0)])[0].track_id
    newcomer, existing = detector([box(100), box(5)])
    assert existing.track_id == track_id
    assert newcomer.track_id != track_id


def test_pop_lost_track_ids_reports_expired_tracks_once(detector):
    track_id = detector([box(0)])[0].track_id
    assert detector.manager.pop_lost_track_ids() == []
    for _ in range(MAX_MISSED_FRAMES + 1):
        detector([])
    lost = detector.manager.pop_lost_track_ids()
    assert lost == [track_id]
    assert detector.manager.pop_lost_track_ids() == []


def test_boxes_clipped_to_original_frame(detector):
    candidate = box(0)
    candidate.xyxy = np.array([[-5, -10, 180, 100]])
    bbox = detector([candidate])[0].bbox
    assert (bbox.x1, bbox.y1, bbox.x2, bbox.y2) == (0, 0, 160, 80)


@pytest.mark.parametrize('coords', [[5, 2, 5, 9], [10, 5, 1, 9], [200, 0, 220, 40], [0, 0, float('nan'), 10]])
def test_invalid_boxes_discarded(detector, coords):
    candidate = box(0)
    candidate.xyxy = np.array([coords])
    assert detector([candidate]) == []


@pytest.mark.parametrize('confidence', [0.49, 0.5, float('nan'), float('inf'), 1.1])
def test_invalid_or_low_confidence(detector, confidence):
    assert detector([box(0, confidence)]) == []


def test_above_threshold(detector):
    assert len(detector([box(0, 0.5001)])) == 1


@pytest.mark.parametrize('frame', [None, np.zeros((10, 10, 3)), np.zeros((10, 10), dtype=np.uint8)])
def test_invalid_frame(detector, frame):
    with pytest.raises(ValueError):
        detector.manager.process(frame)


def test_model_loaded_once_and_predict_settings(monkeypatch):
    from unittest.mock import Mock
    model = Mock()
    model.predict.return_value = [SimpleNamespace(boxes=[])]
    loader = Mock(return_value=model)
    monkeypatch.setitem(sys.modules, 'ultralytics', SimpleNamespace(YOLO=loader))
    manager = YoloDetectorManager('weights.pt')
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    manager.process(frame)
    manager.process(frame)
    loader.assert_called_once_with('weights.pt')
    assert model.predict.call_args.kwargs == dict(verbose=False, classes=[0], conf=0.5)
