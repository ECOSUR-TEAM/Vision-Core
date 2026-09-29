from abc import ABC, abstractmethod
from typing import Optional

from domain.entities import Event


class DoorAnalytics(ABC):
    """VC-DOORLOGIC (Melissa): polígonos ROI (zona exterior/interior) +
    historial de coordenadas por person_id para detectar cruces.

    update() se llama con la posición actual (center del bbox) de un
    person_id ya resuelto por ReIDMemory. Devuelve un Event si el
    historial de esa persona implica un cruce
    (EventType.PERSON_ENTERED / PERSON_EXITED / FALSE_ALARM),
    o None si aún no hay evento que emitir.
    """

    @abstractmethod
    def update(self, person_id: str, position: tuple[float, float]) -> Optional[Event]:
        ...