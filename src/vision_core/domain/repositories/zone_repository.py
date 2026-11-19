from abc import ABC, abstractmethod


class ZoneRepository(ABC):
    @abstractmethod
    def save(self, name: str, points: tuple[tuple[float, float], ...], updated_at: float) -> bool:
        """Upsert a configured zone polygon."""

    @abstractmethod
    def list(self) -> tuple[tuple[str, tuple[tuple[float, float], ...], float], ...]:
        """Return zones as (name, points, updated_at)."""

    @abstractmethod
    def delete_older_than(self, timestamp: float) -> int:
        """Delete zone definitions older than the timestamp (normally unused)."""
