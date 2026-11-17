import numpy as np

from domain.model.bbox import BBox
from domain.model.detection import Detection
from infrastructure.detection.motion_tracker import MotionTracker


def detection(x: float) -> Detection:
    return Detection(BBox(x, 0, x + 20, 40), 0, 0.9, -1)


def test_tracker_assigns_ids_and_survives_motion_without_yolo():
    tracker = MotionTracker()
    first = detection(0)
    tracker.update([first])
    track_id = first.track_id

    tracker.update([detection(5)])
    assert first.track_id == track_id

    tracker.update([])
    resumed = detection(15)
    tracker.update([resumed])
    assert resumed.track_id == track_id


def test_tracker_reports_lost_ids_once():
    tracker = MotionTracker()
    first = detection(0)
    tracker.update([first])

    for _ in range(31):
        tracker.update([])

    assert tracker.pop_lost_track_ids() == [first.track_id]
    assert tracker.pop_lost_track_ids() == []
