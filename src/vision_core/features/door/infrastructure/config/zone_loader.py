import json
from pathlib import Path

from vision_core.features.door.infrastructure.config.zone_config import ZoneConfig
from vision_core.features.door.infrastructure.polygon_validation import (
    validate_polygon,
    validate_vertices_in_frame,
)
from vision_core.shared.domain.polygon import Polygon


def load_zones(path: str | Path) -> ZoneConfig:
    data = json.loads(Path(path).read_text())
    width, height = _parse_frame_size(data)
    polygons = {}
    for name in ("door", "exterior", "interior"):
        polygon = Polygon(name, tuple(tuple(p) for p in data[name]))
        validate_polygon(polygon)
        validate_vertices_in_frame(polygon, width, height)
        polygons[name] = polygon
    return ZoneConfig(width, height, **polygons)


def _parse_frame_size(data: dict[str, object]) -> tuple[int, int]:
    size = data.get("frame_size")
    if not isinstance(size, (list, tuple)) or len(size) != 2:
        raise ValueError("frame_size debe ser [ancho, alto]")
    width, height = size
    if (
        not isinstance(width, int)
        or isinstance(width, bool)
        or not isinstance(height, int)
        or isinstance(height, bool)
        or min(width, height) <= 0
    ):
        raise ValueError("frame_size debe ser [ancho, alto] positivo")
    return width, height
