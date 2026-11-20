from abc import ABC, abstractmethod


class TrackRepository(ABC):
    @abstractmethod
    def append(
        self,
        session_id: str,
        track_id: int,
        person_id: str,
        bbox: tuple[float, float, float, float],
        timestamp: float,
    ) -> bool:
        """Persist a local track sample linked to a persistent person."""

    @abstractmethod
    def list(
        self,
        *,
        session_id: str | None = None,
        since: float | None = None,
        limit: int | None = None,
    ) -> tuple[tuple[str, int, str, tuple[float, float, float, float], float], ...]:
        """Return track samples ordered by timestamp."""

    @abstractmethod
    def delete_older_than(self, timestamp: float) -> int:
        """Delete track samples older than the UTC epoch timestamp."""
