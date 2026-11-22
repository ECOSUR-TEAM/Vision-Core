import math

from vision_core.core.errors import ZoneConfigurationError, codes
from vision_core.features.door.infrastructure.geometry import cross, on_segment


def validate_polygon(polygon):
    pts = polygon.points
    if len(pts) < 3:
        raise ZoneConfigurationError("un polígono necesita al menos 3 puntos", code=codes.ZONE_GEOMETRY_INVALID)
    if any(len(p) != 2 or not all(math.isfinite(v) for v in p) for p in pts):
        raise ZoneConfigurationError("Coordenadas inválidas", code=codes.ZONE_GEOMETRY_INVALID)
    if len(set(pts)) != len(pts):
        raise ZoneConfigurationError("Vértices repetidos", code=codes.ZONE_GEOMETRY_INVALID)
    edges = list(zip(pts, pts[1:] + pts[:1]))
    if abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in edges)) < 1e-9:
        raise ZoneConfigurationError("Polígono sin área", code=codes.ZONE_GEOMETRY_INVALID)
    for i, (a, b) in enumerate(edges):
        for j, (c, d) in enumerate(edges):
            if j <= i or j == i + 1 or (i == 0 and j == len(edges) - 1):
                continue
            if (cross(a, b, c) * cross(a, b, d) < 0 and cross(c, d, a) * cross(c, d, b) < 0) or any(
                [on_segment(a, b, c), on_segment(a, b, d), on_segment(c, d, a), on_segment(c, d, b)]
            ):
                raise ZoneConfigurationError("El polígono se cruza consigo mismo", code=codes.ZONE_GEOMETRY_INVALID)


def validate_vertices_in_frame(polygon, width, height):
    if any(not (0 <= x < width and 0 <= y < height) for x, y in polygon.points):
        raise ZoneConfigurationError(
            f"{polygon.name}: vértices fuera de la imagen",
            code=codes.ZONE_GEOMETRY_INVALID,
        )
