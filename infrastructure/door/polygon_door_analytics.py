from typing import Optional

from domain.entities import Event, Polygon
from domain.ports import DoorAnalytics


class PolygonDoorAnalytics(DoorAnalytics):
    """VC-DOORLOGIC (Melissa).

    TODO:
    - Guardar historial de posiciones por person_id.
    - Point-in-polygon contra exterior_zone / interior_zone.
    - Secuencia exterior->interior = PERSON_ENTERED,
      interior->exterior = PERSON_EXITED,
      toque en exterior sin llegar a interior = FALSE_ALARM.
    """

    def __init__(self, exterior_zone: Polygon, interior_zone: Polygon) -> None:
        self._exterior = exterior_zone
        self._interior = interior_zone
        self._history: dict[str, list[tuple[float, float]]] = {}

    def update(self, person_id: str, position: tuple[float, float]) -> Optional[Event]:
        raise NotImplementedError
