import numpy as np
import pytest

from tests.fakes.fake_detector import FakeDetector
from tests.fakes.fake_door import FakeDoor
from tests.fakes.fake_reid import FakeReID
from tests.fakes.fake_video_source import FakeVideoSource
from vision_core.core.domain.bbox import BBox
from vision_core.features.detection.domain.entities.detection import Detection
from vision_core.features.pipeline.application.dto.request.request_process_frame import RequestProcessFrame
from vision_core.features.pipeline.application.use_cases.run_pipeline import RunPipeline
from vision_core.features.reid.infrastructure.adapters import memory_reid
from vision_core.features.reid.infrastructure.adapters.memory_reid import InMemoryReID


def test_run_emits_event_per_frame():
    events = []
    frame = np.zeros((20, 20, 3), dtype=np.uint8)

    app = RunPipeline(
        video=FakeVideoSource([frame]),
        detector=FakeDetector(),
        reid=FakeReID(),
        door=FakeDoor(),
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

    app = RunPipeline(
        video=FakeVideoSource([frame, frame]),
        detector=detector,
        reid=reid,
        door=FakeDoor(),
        embedder=lambda crop: np.zeros(4),
        on_event=lambda e: None,
    )
    app.run()

    assert reid.lost_calls == ["person-1"]


@pytest.mark.parametrize("elapsed,recovered", [(59.999, True), (60, False), (61, False)])
def test_pipeline_reappearance_ttl_and_cleanup(monkeypatch, elapsed, recovered):
    now = [100.0]
    monkeypatch.setattr(memory_reid.time, "monotonic", lambda: now[0])
    first = Detection(BBox(0, 0, 10, 10), 0, 0.9, 1)
    returned = Detection(BBox(0, 0, 10, 10), 0, 0.9, 2)
    detector = FakeDetector([[first], [first], [], [returned]], [[], [], [1, 1, 999], []])
    memory = InMemoryReID()
    # The latest embedding differs from the first, so matching proves it was retained.
    embeddings = iter([np.array([0.0, 1.0]), np.array([1.0, 0.0]), np.array([1.0, 0.0])])
    app = RunPipeline(
        FakeVideoSource([]), detector, memory, FakeDoor(), lambda crop: next(embeddings), lambda event: None
    )
    frame = np.zeros((20, 20, 3), dtype=np.uint8)
    app._process_frame(frame)
    original = app._person_by_track[1]
    app._process_frame(frame)
    now[0] = 200.0  # TTL starts at expiry, not the first observation.
    app._process_frame(frame)
    assert app._person_by_track == {}
    assert app._last_embedding_by_track == {}
    assert memory._active == {}
    np.testing.assert_array_equal(memory._lost[original][0], [1.0, 0.0])
    assert memory._lost[original][1] == 200.0
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
    app = RunPipeline(
        FakeVideoSource([]), detector, memory, FakeDoor(), lambda crop: np.array([1.0, 0.0]), lambda event: None
    )
    frame = np.zeros((20, 20, 3), dtype=np.uint8)
    app._process_frame(frame)
    original = app._person_by_track[1]
    app._process_frame(frame)
    assert app._person_by_track == {2: original}
    assert set(app._last_embedding_by_track) == {2}
    assert memory._active == {2: original}
    assert memory._lost == {}


def test_reappearance_before_tracker_expiry_recovers_identity():
    first = Detection(BBox(0, 0, 10, 10), 0, 0.9, 1)
    returned = Detection(BBox(10, 0, 20, 10), 0, 0.9, 2)
    memory = InMemoryReID(ttl_seconds=0)
    snapshots = []
    app = RunPipeline(
        FakeVideoSource([np.zeros((20, 20, 3), np.uint8)] * 3),
        FakeDetector([[first], [], [returned]], [[], [], []]),
        memory,
        FakeDoor(),
        lambda crop: np.array([1.0, 0.0]),
        lambda e: None,
        on_frame=lambda frame, tracks, ms: snapshots.append(tracks),
    )
    app.run()
    assert snapshots[0][0].person_id == snapshots[2][0].person_id
    assert len(memory._active) == 1
    assert set(memory._active) == {2}


def test_process_frame_validates_frame_at_the_boundary():
    app = RunPipeline(
        FakeVideoSource([]),
        FakeDetector(),
        FakeReID(),
        FakeDoor(),
        lambda crop: np.zeros(4),
        lambda event: None,
    )

    with pytest.raises(ValueError, match="El frame debe ser un ndarray"):
        app.process_frame(RequestProcessFrame(object()))
