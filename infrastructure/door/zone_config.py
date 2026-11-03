"""Camera pixel coordinates; configuration must match the reference frame."""
import json
import math
from dataclasses import dataclass
from pathlib import Path

from domain.entities import Polygon


def cross(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])


def on_segment(a, b, p):
    return (abs(cross(a, b, p)) <= 1e-9 and
            min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and
            min(a[1], b[1]) <= p[1] <= max(a[1], b[1]))


def validate_polygon(polygon):
    pts = polygon.points
    if len(pts) < 3:
        raise ValueError('un polígono necesita al menos 3 puntos')
    if any(len(p) != 2 or not all(math.isfinite(v) for v in p) for p in pts):
        raise ValueError('Coordenadas inválidas')
    if len(set(pts)) != len(pts):
        raise ValueError('Vértices repetidos')
    edges = list(zip(pts, pts[1:] + pts[:1]))
    if abs(sum(a[0]*b[1]-b[0]*a[1] for a, b in edges)) < 1e-9:
        raise ValueError('Polígono sin área')
    for i, (a, b) in enumerate(edges):
        for j, (c, d) in enumerate(edges):
            if j <= i or j == i+1 or (i == 0 and j == len(edges)-1):
                continue
            if (cross(a,b,c)*cross(a,b,d) < 0 and cross(c,d,a)*cross(c,d,b) < 0) or any([
                on_segment(a,b,c), on_segment(a,b,d), on_segment(c,d,a), on_segment(c,d,b)]):
                raise ValueError('El polígono se cruza consigo mismo')


@dataclass(frozen=True)
class ZoneConfig:
    width: int
    height: int
    door: Polygon
    exterior: Polygon
    interior: Polygon


def load_zones(path):
    data = json.loads(Path(path).read_text())
    width, height = data['frame_size']
    if type(width) is not int or type(height) is not int or min(width, height) <= 0:
        raise ValueError('frame_size debe ser [ancho, alto] positivo')
    polygons = {}
    for name in ('door', 'exterior', 'interior'):
        polygon = Polygon(name, tuple(tuple(p) for p in data[name]))
        validate_polygon(polygon)
        if any(not (0 <= x < width and 0 <= y < height) for x, y in polygon.points):
            raise ValueError(f'{name}: vértices fuera de la imagen')
        polygons[name] = polygon
    return ZoneConfig(width, height, **polygons)
