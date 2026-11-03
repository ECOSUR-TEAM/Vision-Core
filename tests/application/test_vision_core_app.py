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


import pytest
from infrastructure.reid import memory_reid
from infrastructure.reid.memory_reid import InMemoryReID


@pytest.mark.parametrize('elapsed,recovered', [(59.999, True), (60, False), (61, False)])
def test_pipeline_reappearance_ttl_and_cleanup(monkeypatch, elapsed, recovered):
    now = [100.]
    monkeypatch.setattr(memory_reid.time, 'monotonic', lambda: now[0])
    first = Detection(BBox(0, 0, 10, 10), 0, 0.9, 1)
    returned = Detection(BBox(0, 0, 10, 10), 0, 0.9, 2)
    detector = FakeDetector([[first], [first], [], [returned]], [[], [], [1, 1, 999], []])
    memory = InMemoryReID()
    # The latest embedding differs from the first, so matching proves it was retained.
    embeddings = iter([np.array([0., 1.]), np.array([1., 0.]), np.array([1., 0.])])
    app = VisionCoreApp(FakeVideoSource([]), detector, memory, FakeDoor(),
                        lambda crop: next(embeddings), lambda event: None)
    frame = np.zeros((20, 20, 3), dtype=np.uint8)
    app._process_frame(frame)
    original = app._person_by_track[1]
    app._process_frame(frame)
    now[0] = 200.  # TTL starts at expiry, not the first observation.
    app._process_frame(frame)
    assert app._person_by_track == {}
    assert app._last_embedding_by_track == {}
    assert memory._active == {}
    np.testing.assert_array_equal(memory._lost[original][0], [1., 0.])
    assert memory._lost[original][1] == 200.
    now[0] += elapsed
    app._process_frame(frame)
    assert (app._person_by_track[2] == original) == recovered
    assert original not in memory._lost
    assert set(memory._active) == {2}


def test_loss_processed_before_reappearance_in_same_frame():
    first = Detection(BBox(0, 0, 10, 10), 0, 0.9, 1)
    returned = Detection(BBox(0, 0, 10, 10), 0, 0.9, 2)
    detector = FakeDetector([[first], [returned]], [[], [1]])
    memory = InMemoryReID()
    app = VisionCoreApp(FakeVideoSource([]), detector, memory, FakeDoor(),
                        lambda crop: np.array([1., 0.]), lambda event: None)
    frame = np.zeros((20, 20, 3), dtype=np.uint8)
    app._process_frame(frame)
    original = app._person_by_track[1]
    app._process_frame(frame)
    assert app._person_by_track == {2: original}
    assert set(app._last_embedding_by_track) == {2}
    assert memory._active == {2: original}
    assert memory._lost == {}
