from typing import Any

from vision_core.features.monitor.application.dto.request.request_snapshot import RequestSnapshot
from vision_core.features.monitor.application.dto.response.response_snapshot import ResponseSnapshot
from vision_core.features.monitor.application.mappers.monitor_mapper import snapshot_to_response


class GetSnapshot:
    def __init__(self, state: Any) -> None:
        self._state = state

    def execute(self, request: RequestSnapshot) -> ResponseSnapshot:
        return snapshot_to_response(self._state.snapshot())
