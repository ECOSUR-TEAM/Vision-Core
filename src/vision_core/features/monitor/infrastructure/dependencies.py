from dataclasses import dataclass
from pathlib import Path

from vision_core.features.monitor.application.use_cases.get_frame import GetFrame
from vision_core.features.monitor.application.use_cases.get_snapshot import GetSnapshot
from vision_core.features.monitor.application.use_cases.publish_monitor_state import PublishMonitorState
from vision_core.features.monitor.infrastructure.http.server import make_server
from vision_core.features.monitor.infrastructure.state import MonitorState


@dataclass(frozen=True)
class MonitorDependencies:
    state: MonitorState
    publish: PublishMonitorState
    get_snapshot: GetSnapshot
    get_frame: GetFrame

    def make_server(self, host, port, page_path: str | Path | None = None):
        return make_server(host, port, self.state, page_path)


def build_monitor(
    *,
    state=None,
    demo=False,
    event_serializer=None,
    metrics=None,
    health=None,
    camera_id: str = "default",
) -> MonitorDependencies:
    state = state or MonitorState(
        demo=demo,
        event_serializer=event_serializer,
        metrics=metrics,
        health=health,
        camera_id=camera_id,
    )
    return MonitorDependencies(
        state=state,
        publish=PublishMonitorState(state),
        get_snapshot=GetSnapshot(state),
        get_frame=GetFrame(state),
    )
