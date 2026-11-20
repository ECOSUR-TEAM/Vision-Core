from abc import ABC, abstractmethod


class ZoneObservationRepository(ABC):
    @abstractmethod
    def append(
        self,
        person_id: str,
        zone: str,
        position: tuple[float, float],
        timestamp: float,
        event_id: str | None = None,
    ) -> bool:
        """Persist a zone observation and return False when it is a duplicate."""

    @abstractmethod
    def list(
        self,
        *,
        person_id: str | None = None,
        since: float | None = None,
        limit: int | None = None,
    ) -> tuple[tuple[str, str, tuple[float, float], float], ...]:
        """Return observations as (person_id, zone, position, timestamp)."""

    @abstractmethod
    def delete_older_than(self, timestamp: float) -> int:
        """Delete observations older than the UTC epoch timestamp."""
