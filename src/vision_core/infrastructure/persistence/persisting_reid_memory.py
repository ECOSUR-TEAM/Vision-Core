import time
from collections.abc import Callable, Sequence

from vision_core.domain.model.bbox import BBox
from vision_core.domain.ports.reid_memory import ReIDMemory
from vision_core.domain.types import Embedding


class PersistingReIDMemory(ReIDMemory):
    def __init__(
        self,
        inner: ReIDMemory,
        save_identity: Callable[[str, Embedding, float], bool],
        *,
        list_identities: Callable[..., Sequence[tuple[str, Sequence[float], float]]] | None = None,
        identity_ttl_seconds: float = 24 * 3600,
        clock=time.time,
    ):
        self._inner = inner
        self._save_identity = save_identity
        self._clock = clock
        self._track_identity: dict[int, str] = {}
        if list_identities is not None:
            restore = getattr(inner, "restore", None)
            if restore is not None:
                since = clock() - identity_ttl_seconds
                for person_id, embedding, _ in list_identities(since=since):
                    restore(person_id, embedding)

    def begin_frame(self, visible_track_ids: set[int]) -> None:
        self._inner.begin_frame(visible_track_ids)

    def resolve(self, track_id: int, embedding: Embedding, bbox: BBox) -> str:
        person_id = self._inner.resolve(track_id, embedding, bbox)
        if self._track_identity.get(track_id) != person_id:
            self._track_identity[track_id] = person_id
            self._save_identity(person_id, embedding, self._clock())
        return person_id

    def mark_lost(self, person_id: str, embedding: Embedding) -> None:
        self._inner.mark_lost(person_id, embedding)
        self._track_identity = {
            track: identity for track, identity in self._track_identity.items() if identity != person_id
        }
        self._save_identity(person_id, embedding, self._clock())
