"""Carga de la configuración de zonas con validación estricta previa a la geometría."""

from pathlib import Path

from vision_core.core.domain.polygon import Polygon
from vision_core.core.errors import ZoneConfigurationError
from vision_core.features.door.infrastructure.config.zone_config import ZoneConfig
from vision_core.features.door.infrastructure.config.zone_schema import ZONE_NAMES, load_validated_zone_document
from vision_core.features.door.infrastructure.polygon_validation import (
    validate_polygon,
    validate_vertices_in_frame,
)


def load_zones(path: str | Path) -> ZoneConfig:
    try:
        document = load_validated_zone_document(path)
        width, height = document["frame_size"]

        polygons = {}
        for name in ZONE_NAMES:
            try:
                polygon = Polygon(name, document[name])
                validate_polygon(polygon)
                validate_vertices_in_frame(polygon, width, height)
            except ZoneConfigurationError as exc:
                message = str(exc)
                if message.startswith(f"{name}:"):
                    raise
                raise ZoneConfigurationError(
                    f"{name}: {message}",
                    code=exc.code,
                    retryable=exc.retryable,
                    context=exc.context,
                ) from None
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                raise ZoneConfigurationError(f"{name}: {exc}") from None
            polygons[name] = polygon

        return ZoneConfig(width, height, **polygons)
    except ZoneConfigurationError:
        raise
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ZoneConfigurationError(f"configuración de zonas inválida: {exc}") from None
