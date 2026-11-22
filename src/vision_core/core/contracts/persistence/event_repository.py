from abc import ABC, abstractmethod

from vision_core.core.domain.event import Event


class EventRepository(ABC):
    @abstractmethod
    def append(self, event: Event, session_id: str | None = None) -> bool:
        """Persist an event once; return False when its event_id already exists."""

    @abstractmethod
    def list(
        self,
        *,
        person_id: str | None = None,
        session_id: str | None = None,
        since: float | None = None,
        limit: int | None = None,
    ) -> tuple[Event, ...]:
        """Return persisted events ordered by timestamp."""

    @abstractmethod
    def delete_older_than(self, timestamp: float) -> int:
        """Delete events older than the UTC epoch timestamp and return the count."""
