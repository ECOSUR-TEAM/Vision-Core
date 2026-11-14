import math
import time
from collections import deque
from typing import Optional, NamedTuple

from .zone_config import validate_polygon, on_segment

from domain.model.event import Event
from domain.model.polygon import Polygon
from domain.ports import DoorAnalytics


class ZoneObservation(NamedTuple):
    position: tuple[float, float]
    zone: str
    timestamp: float


class PolygonDoorAnalytics(DoorAnalytics):
    """VC-DOORLOGIC (Melissa).

    Determina la zona (interior/exterior/fuera) de cada posición reportada,
    mantiene un historial por person_id, y emite un Event solo cuando hay
    una transición de zona relevante (PERSON_ENTERED, PERSON_EXITED,
    FALSE_ALARM).
    """

    def __init__(self, exterior_zone: Polygon, interior_zone: Polygon, door_zone: Polygon | None = None, *, confirmation_frames: int = 3, history_limit: int = 300) -> None:
        if exterior_zone is None or interior_zone is None:
            raise ValueError("exterior_zone e interior_zone son obligatorios")
        if len(exterior_zone.points) < 3 or len(interior_zone.points) < 3:
            raise ValueError("un polígono necesita al menos 3 puntos")
        for polygon in (exterior_zone, interior_zone, door_zone):
            if polygon is not None:
                validate_polygon(polygon)
        if type(confirmation_frames) is not int or confirmation_frames < 1:
            raise ValueError("confirmation_frames debe ser un entero positivo")
        if type(history_limit) is not int or history_limit < 1:
            raise ValueError("history_limit debe ser un entero positivo")
        self._confirmation_frames = confirmation_frames
        self._history_limit = history_limit
        self._pending: dict[str, tuple[str, int]] = {}
        self._door = door_zone
        self._exterior = exterior_zone
        self._interior = interior_zone
        self._history: dict[str, deque[ZoneObservation]] = {}
        self._last_zone: dict[str, str] = {}

    @staticmethod
    def _point_in_polygon(point: tuple[float, float], polygon: Polygon) -> bool:
        x, y = point
        inside = False
        pts = polygon.points
        if any(on_segment(a, b, point) for a, b in zip(pts, pts[1:] + pts[:1])):
            return True
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

    def get_history(self, person_id: str) -> tuple[ZoneObservation, ...]:
        """Immutable snapshot of recent observations, including unconfirmed noise."""
        return tuple(self._history.get(person_id, ()))

    def update(self, person_id: str, position: tuple[float, float]) -> Optional[Event]:
        if len(position) != 2 or not all(math.isfinite(value) for value in position):
            raise ValueError("La posición debe tener dos coordenadas finitas")
        position = tuple(position)
        zone = self._zone_for(position)
        timestamp = time.time()
        self._history.setdefault(person_id, deque(maxlen=self._history_limit)).append(
            ZoneObservation(position, zone, timestamp))
        previous_zone = self._last_zone.get(person_id)
        if zone == previous_zone:
            self._pending.pop(person_id, None)
            return None
        pending_zone, count = self._pending.get(person_id, (zone, 0))
        count = count + 1 if pending_zone == zone else 1
        self._pending[person_id] = (zone, count)
        if count < self._confirmation_frames:
            return None
        self._pending.pop(person_id, None)
        self._last_zone[person_id] = zone
        event_type = {
            ("exterior", "interior"): "PERSON_ENTERED",
            ("interior", "exterior"): "PERSON_EXITED",
            ("exterior", "fuera"): "FALSE_ALARM",
        }.get((previous_zone, zone))
        if event_type is None:
            return None
        return Event(event=event_type, person_id=person_id, timestamp=timestamp,
                     metadata={"from_zone": previous_zone, "to_zone": zone,
                               "position": position,
                               "confirmation_frames": self._confirmation_frames})
