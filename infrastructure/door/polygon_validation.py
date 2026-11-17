"""Validation rules for polygons defined on a camera reference frame."""
import math

from .geometry import cross, on_segment


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


def validate_vertices_in_frame(polygon, width, height):
    if any(not (0 <= x < width and 0 <= y < height) for x, y in polygon.points):
        raise ValueError(f'{polygon.name}: vértices fuera de la imagen')
