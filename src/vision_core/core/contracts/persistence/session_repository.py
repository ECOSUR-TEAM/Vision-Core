from abc import ABC, abstractmethod


class SessionRepository(ABC):
    @abstractmethod
    def start(self, session_id: str, started_at: float, camera_id: str | None = None) -> bool:
        """Create a processing session if it does not exist yet."""

    @abstractmethod
    def finish(self, session_id: str, finished_at: float) -> bool:
        """Record the end of a session."""

    @abstractmethod
    def list(
        self, *, since: float | None = None, limit: int | None = None
    ) -> tuple[tuple[str, float, float | None, str | None], ...]:
        """Return sessions as (session_id, started_at, finished_at, camera_id)."""

    @abstractmethod
    def delete_older_than(self, timestamp: float) -> int:
        """Delete sessions older than the UTC epoch timestamp."""
