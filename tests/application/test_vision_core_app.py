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
    def process(self, frame):
        return [Detection(bbox=BBox(0, 0, 10, 10), class_id=0, confidence=0.9, track_id=1)]


class FakeReID:
    def resolve(self, track_id, embedding, bbox):
        return "person-1"

    def mark_lost(self, person_id, embedding):
        pass


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
