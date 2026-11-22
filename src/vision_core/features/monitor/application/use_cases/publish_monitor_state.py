from typing import Any


class PublishMonitorState:
    def __init__(self, state: Any) -> None:
        self._state = state

    def execute(self, jpeg, people, processing_ms, dropped=0, queue_size=0, camera_id: str | None = None) -> None:
        if camera_id is None:
            self._state.publish(jpeg, people, processing_ms, dropped, queue_size)
            return
        self._state.publish(jpeg, people, processing_ms, dropped, queue_size, camera_id=camera_id)

    def publish_event(self, event) -> None:
        self._state.event(event)
