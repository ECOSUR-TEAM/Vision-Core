import time
from collections.abc import Callable

from vision_core.domain.model.bbox import BBox
from vision_core.domain.ports.reid_memory import ReIDMemory
from vision_core.domain.types import Embedding


class PersistingReIDMemory(ReIDMemory):
    def __init__(
        self,
        inner: ReIDMemory,
        save_identity: Callable[[str, Embedding, float], bool],
        *,
        clock=time.time,
    ):
        self._inner = inner
        self._save_identity = save_identity
        self._clock = clock

    def begin_frame(self, visible_track_ids: set[int]) -> None:
        self._inner.begin_frame(visible_track_ids)

    def resolve(self, track_id: int, embedding: Embedding, bbox: BBox) -> str:
        person_id = self._inner.resolve(track_id, embedding, bbox)
        self._save_identity(person_id, embedding, self._clock())
        return person_id

    def mark_lost(self, person_id: str, embedding: Embedding) -> None:
        self._inner.mark_lost(person_id, embedding)
        self._save_identity(person_id, embedding, self._clock())
