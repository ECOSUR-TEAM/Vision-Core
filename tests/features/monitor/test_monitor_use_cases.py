from vision_core.features.monitor.application.dto.request.request_frame import RequestFrame
from vision_core.features.monitor.application.dto.request.request_snapshot import RequestSnapshot
from vision_core.features.monitor.application.use_cases.get_frame import GetFrame
from vision_core.features.monitor.application.use_cases.get_snapshot import GetSnapshot
from vision_core.features.monitor.application.use_cases.publish_monitor_state import PublishMonitorState
from vision_core.shared.application.dto.serialization import dumps_json


class FakeMonitorState:
    def __init__(self):
        self.published = []

    def publish(self, jpeg, people, processing_ms, dropped, queue_size=0):
        self.published.append((jpeg, people, processing_ms, dropped))

    def snapshot(self):
        return {
            "status": "running",
            "error": None,
            "demo_zones": False,
            "frame": 4,
            "updated_at": 10.0,
            "age_seconds": 0.1,
            "people": [],
            "events": [],
            "counts": {},
            "processing_ms": 2.0,
            "fps": 15.0,
            "dropped_frames": 0,
        }

    def current_frame(self):
        return b"jpeg", 4

    def next_frame(self, after):
        return (b"next", after + 1)


def test_publish_and_read_use_cases_use_injected_state():
    state = FakeMonitorState()
    PublishMonitorState(state).execute(b"jpeg", [], 2.0)

    snapshot = GetSnapshot(state).execute(RequestSnapshot())
    frame = GetFrame(state).execute(RequestFrame())
    next_frame = GetFrame(state).execute(RequestFrame(after=4))

    assert state.published == [(b"jpeg", [], 2.0, 0)]
    assert snapshot.frame == 4
    assert frame.jpeg == b"jpeg"
    assert next_frame.sequence == 5
    dumps_json(snapshot)
