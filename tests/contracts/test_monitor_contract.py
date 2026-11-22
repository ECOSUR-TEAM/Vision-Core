import pytest

from tests.fakes.fake_monitor_state import FakeMonitorState
from vision_core.core.domain.event import Event
from vision_core.core.serialization import EVENT_SCHEMA_VERSION
from vision_core.features.monitor.application.dto.request.request_frame import RequestFrame
from vision_core.features.monitor.application.dto.request.request_snapshot import RequestSnapshot
from vision_core.features.monitor.application.use_cases.get_frame import GetFrame
from vision_core.features.monitor.application.use_cases.get_snapshot import GetSnapshot
from vision_core.features.monitor.application.use_cases.publish_monitor_state import PublishMonitorState
from vision_core.features.monitor.infrastructure.state import MonitorState


@pytest.mark.parametrize("factory", [MonitorState, FakeMonitorState])
def test_monitor_state_port_contract_with_fake_and_real_implementation(factory):
    state = factory()
    for method in ("set_status", "event", "person_label", "publish", "current_frame", "next_frame", "snapshot"):
        assert callable(getattr(state, method))

    publish = PublishMonitorState(state)
    publish.execute(b"jpeg", (), 2.0, 0)
    publish.publish_event(Event(event="PERSON_ENTERED", person_id="persona-1"))

    snapshot = GetSnapshot(state).execute(RequestSnapshot())
    frame = GetFrame(state).execute(RequestFrame())
    assert snapshot is not None
    assert frame is not None


def test_real_monitor_events_expose_current_schema_version():
    state = MonitorState()
    state.event(Event(event="PERSON_ENTERED", person_id="persona-1"))
    snapshot = GetSnapshot(state).execute(RequestSnapshot())
    assert snapshot.events
    assert snapshot.events[0].schema_version == EVENT_SCHEMA_VERSION
