from typing import Any


class PublishMonitorState:
    def __init__(self, state: Any) -> None:
        self._state = state

    def execute(self, jpeg, people, processing_ms, dropped=0) -> None:
        self._state.publish(jpeg, people, processing_ms, dropped)

    def publish_event(self, event) -> None:
        self._state.event(event)

