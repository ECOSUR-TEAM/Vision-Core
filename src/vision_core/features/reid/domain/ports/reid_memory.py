from typing import Any, Protocol

from vision_core.shared.domain.bbox import BBox


class ReIDMemory(Protocol):
    def begin_frame(self, visible_track_ids: set[int]) -> None: ...

    def resolve(self, track_id: int, embedding: Any, bbox: BBox) -> str: ...

    def mark_lost(self, person_id: str, embedding: Any) -> None: ...
