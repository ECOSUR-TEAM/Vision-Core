from typing import Optional

from domain.entities import Event, Polygon
from domain.ports import DoorAnalytics


class PolygonDoorAnalytics(DoorAnalytics):
    """VC-DOORLOGIC (Melissa).

    TODO:
    - Clasificar evento en update(): secuencia exterior->interior = PERSON_ENTERED,
      interior->exterior = PERSON_EXITED, toque en exterior sin llegar a
      interior = FALSE_ALARM. Devolver Event solo en la transición.
    """

    def __init__(self, exterior_zone: Polygon, interior_zone: Polygon) -> None:
        if exterior_zone is None or interior_zone is None:
            raise ValueError("exterior_zone e interior_zone son obligatorios")
        if len(exterior_zone.points) < 3 or len(interior_zone.points) < 3:
            raise ValueError("un polígono necesita al menos 3 puntos")
        self._exterior = exterior_zone
        self._interior = interior_zone
        self._history: dict[str, list[tuple[tuple[float, float], str]]] = {}

    @staticmethod
    def _point_in_polygon(point: tuple[float, float], polygon: Polygon) -> bool:
        x, y = point
        inside = False
        pts = polygon.points
        n = len(pts)
        p1x, p1y = pts[0]
        for i in range(1, n + 1):
            p2x, p2y = pts[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        return inside

    def _zone_for(self, position: tuple[float, float]) -> str:
        if self._point_in_polygon(position, self._interior):
            return "interior"
        if self._point_in_polygon(position, self._exterior):
            return "exterior"
        return "fuera"

    def update(self, person_id: str, position: tuple[float, float]) -> Optional[Event]:
        zone = self._zone_for(position)
        if person_id not in self._history:
            self._history[person_id] = []
        self._history[person_id].append((position, zone))
        return None
