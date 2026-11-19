import json
from pathlib import Path

from vision_core.features.door.infrastructure.config.zone_config import ZoneConfig
from vision_core.features.door.infrastructure.polygon_validation import (
    validate_polygon,
    validate_vertices_in_frame,
)
from vision_core.shared.domain.polygon import Polygon
from vision_core.shared.errors import ZoneConfigurationError


def load_zones(path: str | Path) -> ZoneConfig:
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
            points = tuple(tuple(p) for p in data[name])
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


def _parse_frame_size(data: dict[str, object]) -> tuple[int, int]:
    try:
        width, height = data["frame_size"]
    except (KeyError, TypeError) as error:
        raise ZoneConfigurationError("Falta frame_size en la configuración de zonas.") from error
    if (
        not isinstance(width, int)
        or isinstance(width, bool)
        or not isinstance(height, int)
        or isinstance(height, bool)
        or min(width, height) <= 0
    ):
        raise ZoneConfigurationError("frame_size debe ser [ancho, alto] positivo")
    return width, height
