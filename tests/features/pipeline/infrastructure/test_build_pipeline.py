import numpy as np

from tests.fakes.fake_detector import FakeDetector
from tests.fakes.fake_door import FakeDoor
from tests.fakes.fake_reid import FakeReID
from tests.fakes.fake_video_source import FakeVideoSource
from vision_core.features.pipeline.application.dto.request.request_process_frame import RequestProcessFrame
from vision_core.features.pipeline.application.use_cases.run_pipeline import RunPipeline
from vision_core.features.pipeline.infrastructure.dependencies import build_pipeline


def test_build_pipeline_wires_all_port_fakes():
    events = []
    frame = np.zeros((20, 20, 3), dtype=np.uint8)
    app = build_pipeline(
        FakeVideoSource([frame]),
        FakeDetector(),
        FakeReID(),
        FakeDoor(),
        lambda crop: np.ones(4),
        events.append,
    )

    app.run()

    assert isinstance(app, RunPipeline)
    assert len(events) == 1
    assert events[0].event == "PERSON_ENTERED"


def test_build_pipeline_forwards_frame_observer():
    snapshots = []
    app = build_pipeline(
        FakeVideoSource([]),
        FakeDetector(),
        FakeReID(),
        FakeDoor(),
        lambda crop: np.ones(4),
        lambda event: None,
        on_frame=lambda frame, tracks, ms: snapshots.append(tracks),
    )

    app._process_frame(np.zeros((20, 20, 3), dtype=np.uint8))

    assert snapshots[0][0].person_id == "person-1"


def test_process_frame_returns_serializable_response():
    app = build_pipeline(
        FakeVideoSource([]),
        FakeDetector(),
        FakeReID(),
        FakeDoor(),
        lambda crop: np.ones(4),
        lambda event: None,
    )

    response = app.process_frame(RequestProcessFrame(np.zeros((20, 20, 3), dtype=np.uint8)))

    assert response.people[0]["person_id"] == "person-1"
    assert response.events[0]["event"] == "PERSON_ENTERED"
    assert response.processing_ms >= 0
