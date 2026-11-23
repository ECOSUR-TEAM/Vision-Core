"""Validación geométrica de zonas, delegada al validador compartido del core."""

from vision_core.core.domain.polygon import Polygon
from vision_core.core.validation.zone_payload import validate_polygon_bounds, validate_polygon_points


def validate_polygon(polygon: Polygon) -> None:
    validate_polygon_points(polygon.name, polygon.points)


def validate_vertices_in_frame(polygon: Polygon, width: int, height: int) -> None:
    validate_polygon_bounds(polygon.name, polygon.points, width, height)
