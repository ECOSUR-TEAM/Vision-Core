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
        if track_id in self._active:
            return self._active[track_id]
        
        now = time.time()

        self._lost = {
            person_id: (stored_embedding, timestamp)
            for person_id, (stored_embedding, timestamp) in self._lost.items()
            if now - timestamp < TTL_SECONDS
        }

        best_person_id = None
        best_similarity = -1.0
        embedding_norm = np.linalg.norm(embedding)

        if embedding_norm > 0:
            for person_id, (stored_embedding, _) in self._lost.items():
                stored_norm = np.linalg.norm(stored_embedding)

                if stored_norm == 0:
                    continue

                similarity = np.dot(embedding, stored_embedding) / (embedding_norm * stored_norm)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = person_id

        if best_similarity > SIMILARITY_THRESHOLD:
            person_id = best_person_id
            self._lost.pop(person_id)
        else:
            person_id = str(uuid.uuid4())

        self._active[track_id] = person_id
        return person_id


    def mark_lost(self, person_id: str, embedding: np.ndarray) -> None:
        self._lost[person_id] = (embedding, time.time())
   
