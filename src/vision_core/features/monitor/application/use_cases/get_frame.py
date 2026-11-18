from typing import Any

from vision_core.features.monitor.application.dto.request.request_frame import RequestFrame
from vision_core.features.monitor.application.dto.response.response_frame import ResponseFrame
from vision_core.features.monitor.application.mappers.monitor_mapper import frame_to_response


class GetFrame:
    def __init__(self, state: Any) -> None:
        self._state = state

    def execute(self, request: RequestFrame) -> ResponseFrame:
        if request.after is None:
            jpeg, sequence = self._state.current_frame()
        else:
            jpeg, sequence = self._state.next_frame(request.after)
        return frame_to_response(jpeg, sequence)
