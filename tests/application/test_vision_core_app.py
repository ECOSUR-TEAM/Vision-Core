import numpy as np

from application.vision_core_app import VisionCoreApp
from domain.entities import BBox, Detection, Event


class FakeVideoSource:
    def __init__(self, frames):
        self._frames = list(frames) + [None]

    def open(self):
        pass

    def read_frame(self):
        return self._frames.pop(0)

    def close(self):
        pass


class FakeDetector:
    def __init__(self, detections_per_frame=None, lost_ids_per_call=None):
        self._detections_per_frame = detections_per_frame
        self._lost_ids_per_call = list(lost_ids_per_call or [])

    def process(self, frame):
        if self._detections_per_frame is not None:
            return self._detections_per_frame.pop(0)
        return [Detection(bbox=BBox(0, 0, 10, 10), class_id=0, confidence=0.9, track_id=1)]

    def pop_lost_track_ids(self):
        return self._lost_ids_per_call.pop(0) if self._lost_ids_per_call else []


class FakeReID:
    def __init__(self):
        self.lost_calls = []

    def resolve(self, track_id, embedding, bbox):
        return "person-1"

    def mark_lost(self, person_id, embedding):
        self.lost_calls.append(person_id)


class FakeDoor:
    def update(self, person_id, position):
        return Event(event="PERSON_ENTERED", person_id=person_id)


def test_run_emits_event_per_frame():
    events = []
    frame = np.zeros((20, 20, 3), dtype=np.uint8)

    app = VisionCoreApp(
        video_source=FakeVideoSource([frame]),
        detector=FakeDetector(),
        reid_memory=FakeReID(),
        door_analytics=FakeDoor(),
        embedder=lambda crop: np.zeros(4),
        on_event=events.append,
    )
    app.run()

    assert len(events) == 1
    assert events[0].event == "PERSON_ENTERED"
    assert events[0].person_id == "person-1"


def test_run_calls_mark_lost_when_track_is_dropped():
    frame = np.zeros((20, 20, 3), dtype=np.uint8)
    det_track_1 = Detection(bbox=BBox(0, 0, 10, 10), class_id=0, confidence=0.9, track_id=1)

    detector = FakeDetector(
        detections_per_frame=[[det_track_1], []],
        lost_ids_per_call=[[], [1]],  # se pierde justo despues del 2do process()
    )
    reid = FakeReID()

    app = VisionCoreApp(
        video_source=FakeVideoSource([frame, frame]),
        detector=detector,
        reid_memory=reid,
        door_analytics=FakeDoor(),
        embedder=lambda crop: np.zeros(4),
        on_event=lambda e: None,
    )
    app.run()

    assert reid.lost_calls == ["person-1"]
