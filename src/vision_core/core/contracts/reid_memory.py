from typing import Protocol, runtime_checkable

from vision_core.core.domain.bbox import BBox
from vision_core.core.domain.types import Embedding


@runtime_checkable
class ReIDMemory(Protocol):
    """VC-REID (Briyan): memoria temporal con TTL + similitud coseno.

    resolve(): dado un track_id local + su embedding visual, devuelve un
    person_id persistente (UUID nuevo, o uno recuperado de la memoria si
    similitud visual suficiente contra una persona ausente).
    """

    def begin_frame(self, visible_track_ids: set[int]) -> None:
        """Reserve retained local tracks before resolving new detections."""

    def resolve(self, track_id: int, embedding: Embedding, bbox: BBox) -> str: ...

    def mark_lost(self, person_id: str, embedding: Embedding) -> None:
        """Se llama al dejar de verse; elimina el mapping activo e inicia el TTL."""
        ...
