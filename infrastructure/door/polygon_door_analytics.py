from typing import Optional

from domain.entities import Event, Polygon
from domain.ports import DoorAnalytics


class PolygonDoorAnalytics(DoorAnalytics):
    """VC-DOORLOGIC (Melissa).

    Determina la zona (interior/exterior/fuera) de cada posición reportada,
    mantiene un historial por person_id, y emite un Event solo cuando hay
    una transición de zona relevante (PERSON_ENTERED, PERSON_EXITED,
    FALSE_ALARM).
    """

    def __init__(self, exterior_zone: Polygon, interior_zone: Polygon) -> None:
        if exterior_zone is None or interior_zone is None:
            raise ValueError("exterior_zone e interior_zone son obligatorios")
        if len(exterior_zone.points) < 3 or len(interior_zone.points) < 3:
            raise ValueError("un polígono necesita al menos 3 puntos")
        self._exterior = exterior_zone
        self._interior = interior_zone
        self._history: dict[str, list[tuple[tuple[float, float], str]]] = {}
        self._last_zone: dict[str, str] = {}

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
        self._history.setdefault(person_id, []).append((position, zone))

        previous_zone = self._last_zone.get(person_id)

        if zone == previous_zone:
            return None

        event = None
        if previous_zone == "exterior" and zone == "interior":
            event = Event(event="PERSON_ENTERED", person_id=person_id)
        elif previous_zone == "interior" and zone == "exterior":
            event = Event(event="PERSON_EXITED", person_id=person_id)
        elif previous_zone == "exterior" and zone == "fuera":
            event = Event(event="FALSE_ALARM", person_id=person_id)

        self._last_zone[person_id] = zone
        return event