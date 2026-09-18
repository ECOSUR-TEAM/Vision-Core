import time
import uuid
import numpy as np

from domain.entities import BBox
from domain.ports import ReIDMemory

TTL_SECONDS = 60
SIMILARITY_THRESHOLD = 0.85


class InMemoryReID(ReIDMemory):
    """VC-REID (Briyan).

    TODO:
    - Mantener un dict {person_id: (embedding, lost_at)} para ids retirados.
    - En resolve(): si track_id ya está mapeado a un person_id activo, usarlo.
      Si es un track nuevo, comparar su embedding (similitud coseno) contra
      los ids retirados no vencidos (TTL_SECONDS); si supera
      SIMILARITY_THRESHOLD, recuperar ese person_id; si no, generar uuid4.
    - En mark_lost(): guardar (embedding, time.time()) y limpiar vencidos.
    """

    def __init__(self) -> None:
        self._active: dict[int, str] = {}       # track_id local -> person_id
        self._lost: dict[str, tuple[np.ndarray, float]] = {}

    def resolve(self, track_id: int, embedding: np.ndarray, bbox: BBox) -> str:
        raise NotImplementedError

    def mark_lost(self, person_id: str, embedding: np.ndarray) -> None:
        raise NotImplementedError
