from abc import ABC, abstractmethod
from collections.abc import Sequence

from vision_core.domain.types import Embedding


class IdentityRepository(ABC):
    @abstractmethod
    def save(self, person_id: str, embedding: Embedding, last_seen_at: float) -> bool:
        """Upsert the latest embedding for a persistent person identity."""

    @abstractmethod
    def list_active(self, *, since: float) -> tuple[tuple[str, Sequence[float], float], ...]:
        """Return identities seen since the UTC epoch timestamp."""

    @abstractmethod
    def delete_older_than(self, timestamp: float) -> int:
        """Delete identities whose last_seen_at is older than the timestamp."""

    @abstractmethod
    def delete_persons_older_than(self, timestamp: float) -> int:
        """Delete person records whose last_seen is older than the timestamp."""
