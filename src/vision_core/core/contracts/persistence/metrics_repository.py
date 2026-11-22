from abc import ABC, abstractmethod


class MetricsRepository(ABC):
    @abstractmethod
    def record(self, session_id: str, name: str, value: float, timestamp: float) -> bool:
        """Persist a metric sample associated with a session."""

    @abstractmethod
    def list(
        self, *, session_id: str | None = None, since: float | None = None
    ) -> tuple[tuple[str, str, float, float], ...]:
        """Return metrics as (session_id, name, value, timestamp)."""

    @abstractmethod
    def delete_older_than(self, timestamp: float) -> int:
        """Delete metric samples older than the UTC epoch timestamp."""
