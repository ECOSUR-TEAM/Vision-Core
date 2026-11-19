"""Load and validate camera zone configuration files."""

import json
from pathlib import Path

from vision_core.domain.model.polygon import Polygon
from vision_core.shared.errors import ZoneConfigurationError

from .polygon_validation import validate_polygon, validate_vertices_in_frame
from .zone_config import ZoneConfig


def load_zones(path):
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError) as error:
        raise ZoneConfigurationError(
            "No se pudo leer la configuración de zonas.",
            context={"operation": "load_file"},
        ) from error
    width, height = _parse_frame_size(data)
    polygons = {}
    for name in ("door", "exterior", "interior"):
        try:
            points = tuple(tuple(point) for point in data[name])
        except (KeyError, TypeError) as error:
            raise ZoneConfigurationError(
                "Falta un polígono obligatorio en la configuración.",
                context={"zone": name},
            ) from error
        polygon = Polygon(name, points)
        validate_polygon(polygon)
        validate_vertices_in_frame(polygon, width, height)
        polygons[name] = polygon
    return ZoneConfig(width, height, **polygons)


def _parse_frame_size(data):
    try:
        width, height = data["frame_size"]
    except (KeyError, TypeError) as error:
        raise ZoneConfigurationError("Falta frame_size en la configuración de zonas.") from error
    if any(not isinstance(value, int) or isinstance(value, bool) or value <= 0 for value in (width, height)):
        raise ZoneConfigurationError("frame_size debe ser [ancho, alto] positivo")
    return width, height
