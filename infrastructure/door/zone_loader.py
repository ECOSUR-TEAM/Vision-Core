"""Load and validate camera zone configuration files."""
import json
from pathlib import Path

from domain.entities import Polygon

from .polygon_validation import validate_polygon, validate_vertices_in_frame
from .zone_config import ZoneConfig


def load_zones(path):
    data = json.loads(Path(path).read_text())
    width, height = _parse_frame_size(data)
    polygons = {}
    for name in ('door', 'exterior', 'interior'):
        polygon = Polygon(name, tuple(tuple(p) for p in data[name]))
        validate_polygon(polygon)
        validate_vertices_in_frame(polygon, width, height)
        polygons[name] = polygon
    return ZoneConfig(width, height, **polygons)


def _parse_frame_size(data):
    width, height = data['frame_size']
    if type(width) is not int or type(height) is not int or min(width, height) <= 0:
        raise ValueError('frame_size debe ser [ancho, alto] positivo')
    return width, height
