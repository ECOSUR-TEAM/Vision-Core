from abc import ABC, abstractmethod
import numpy as np

from domain.entities import BBox


class ReIDMemory(ABC):
    """VC-REID (Briyan): memoria temporal con TTL + similitud coseno.

    resolve(): dado un track_id local + su embedding visual, devuelve un
    person_id persistente (UUID nuevo, o uno recuperado de la memoria si
    similitud coseno > 0.85 contra un id retirado recientemente).
    """

    @abstractmethod
    def resolve(self, track_id: int, embedding: np.ndarray, bbox: BBox) -> str:
        ...

    @abstractmethod
    def mark_lost(self, person_id: str, embedding: np.ndarray) -> None:
        """Se llama cuando un track deja de verse; arranca su TTL (ej. 60s)."""
        ...
