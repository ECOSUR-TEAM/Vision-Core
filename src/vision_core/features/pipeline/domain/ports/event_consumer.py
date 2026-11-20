from typing import Any, Protocol

from vision_core.shared.domain.event import Event


class EventConsumer(Protocol):
    def __call__(self, event: Event) -> Any: ...
