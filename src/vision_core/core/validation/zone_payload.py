"""Validación compartida del documento de zonas (esquema + geometría + tamaño).

Esta es la única implementación de las reglas del esquema 1.0. La carga desde
archivo, el editor del monitor y los tests delegan aquí; el cliente del monitor
sólo replica las comprobaciones para retroalimentación inmediata y confirma en el
servidor antes de guardar.
"""

import math
from collections.abc import Mapping, Sequence
from typing import Any

from vision_core.core.errors import ZoneConfigurationError, codes
from vision_core.core.serialization import dumps_json

SUPPORTED_ZONE_SCHEMA_VERSION = "1.0"
MAX_ZONE_PAYLOAD_BYTES = 100 * 1024
MAX_ZONE_POINTS = 100
ZONE_NAMES = ("door", "exterior", "interior")
REQUIRED_ZONE_KEYS = ("version", "frame_size", *ZONE_NAMES)


def reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Rechazar claves JSON repetidas en lugar de quedarse con la última."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ZoneConfigurationError(f"clave duplicada no permitida: {key}")
        result[key] = value
    return result


def validate_zone_payload(data: object, *, max_bytes: int = MAX_ZONE_PAYLOAD_BYTES) -> dict[str, Any]:
    """Valida tamaño, esquema y geometría; devuelve el documento normalizado.

    ``ZoneConfigurationError`` es la única salida esperada para datos inválidos,
    de forma que todas las capas traducen el mismo código de error.
    """
    try:
        encoded = dumps_json(data).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as error:
        raise ZoneConfigurationError(f"payload de zonas no serializable: {error}") from None
    if len(encoded) > max_bytes:
        raise ZoneConfigurationError(
            f"el payload de zonas supera el límite de {max_bytes} bytes (tiene {len(encoded)} bytes)"
        )

    document = validate_zone_schema(data)
    validate_zone_geometry(document)
    return document


def validate_zone_schema(data: object) -> dict[str, Any]:
    """Valida claves, versión, ``frame_size`` y coordenadas sin geometría."""
    try:
        return _validate_schema(data)
    except ZoneConfigurationError:
        raise
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        raise ZoneConfigurationError(f"configuración de zonas inválida: {error}") from None


def validate_zone_geometry(document: Mapping[str, Any]) -> None:
    """Aplica las reglas geométricas a las tres zonas del documento validado."""
    width, height = document["frame_size"]
    for name in ZONE_NAMES:
        points = document[name]
        validate_polygon_points(name, points)
        validate_polygon_bounds(name, points, width, height)


def validate_polygon_points(name: str, points: Sequence[tuple[float, float]]) -> None:
    """Comprueba vértices finitos, sin repeticiones, con área y sin cruces."""
    if len(points) < 3:
        raise ZoneConfigurationError(
            f"{name}: un polígono necesita al menos 3 puntos", code=codes.ZONE_GEOMETRY_INVALID
        )
    if any(len(point) != 2 or not all(math.isfinite(value) for value in point) for point in points):
        raise ZoneConfigurationError(f"{name}: Coordenadas inválidas", code=codes.ZONE_GEOMETRY_INVALID)
    if len(set(points)) != len(points):
        raise ZoneConfigurationError(f"{name}: Vértices repetidos", code=codes.ZONE_GEOMETRY_INVALID)

    vertices = tuple(points)
    edges = list(zip(vertices, vertices[1:] + vertices[:1]))
    if abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in edges)) < 1e-9:
        raise ZoneConfigurationError(f"{name}: Polígono sin área", code=codes.ZONE_GEOMETRY_INVALID)
    for index, (a, b) in enumerate(edges):
        for other, (c, d) in enumerate(edges):
            if other <= index or other == index + 1 or (index == 0 and other == len(edges) - 1):
                continue
            if (_cross(a, b, c) * _cross(a, b, d) < 0 and _cross(c, d, a) * _cross(c, d, b) < 0) or any(
                (_on_segment(a, b, c), _on_segment(a, b, d), _on_segment(c, d, a), _on_segment(c, d, b))
            ):
                raise ZoneConfigurationError(
                    f"{name}: El polígono se cruza consigo mismo", code=codes.ZONE_GEOMETRY_INVALID
                )


def validate_polygon_bounds(
    name: str,
    points: Sequence[tuple[float, float]],
    width: int,
    height: int,
) -> None:
    """Comprueba que todos los vértices caen dentro del frame."""
    if any(not (0 <= x < width and 0 <= y < height) for x, y in points):
        raise ZoneConfigurationError(
            f"{name}: vértices fuera de la imagen",
            code=codes.ZONE_GEOMETRY_INVALID,
        )


def zone_document_to_json(document: Mapping[str, Any]) -> dict[str, Any]:
    """Convierte el documento validado a JSON plano para transporte y auditoría."""
    return {
        "version": document["version"],
        "frame_size": list(document["frame_size"]),
        **{name: [list(point) for point in document[name]] for name in ZONE_NAMES},
    }


def _validate_schema(data: object) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ZoneConfigurationError(
            f"la configuración de zonas debe ser un objeto JSON, se recibió {type(data).__name__}"
        )

    _validate_keys(data)
    version = _validate_version(data["version"])
    width, height = _validate_frame_size(data["frame_size"])

    document: dict[str, Any] = {"version": version, "frame_size": (width, height)}
    for name in ZONE_NAMES:
        document[name] = _validate_zone_points(data[name], name)
    return document


def _validate_keys(data: dict[Any, Any]) -> None:
    missing = [key for key in REQUIRED_ZONE_KEYS if key not in data]
    if missing:
        raise ZoneConfigurationError(f"faltan claves requeridas: {', '.join(missing)}")

    unknown = sorted(str(key) for key in data if key not in REQUIRED_ZONE_KEYS)
    if unknown:
        raise ZoneConfigurationError(f"claves desconocidas no permitidas: {', '.join(unknown)}")


def _validate_version(value: object) -> str:
    if not isinstance(value, str):
        raise ZoneConfigurationError(
            f"version: se esperaba la cadena '{SUPPORTED_ZONE_SCHEMA_VERSION}', se recibió {type(value).__name__}"
        )
    if value != SUPPORTED_ZONE_SCHEMA_VERSION:
        raise ZoneConfigurationError(
            f"version: esquema '{value}' no soportado; se espera '{SUPPORTED_ZONE_SCHEMA_VERSION}'"
        )
    return value


def _validate_frame_size(value: object) -> tuple[int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ZoneConfigurationError("frame_size: debe ser una lista o tupla de exactamente 2 enteros positivos")
    return (
        _validate_positive_int(value[0], "frame_size[0]"),
        _validate_positive_int(value[1], "frame_size[1]"),
    )


def _validate_zone_points(value: object, name: str) -> tuple[tuple[float, float], ...]:
    if not isinstance(value, (list, tuple)):
        raise ZoneConfigurationError(f"{name}: debe ser una lista de coordenadas [x, y]")
    if len(value) > MAX_ZONE_POINTS:
        raise ZoneConfigurationError(
            f"{name}: supera el máximo de {MAX_ZONE_POINTS} puntos por zona ({len(value)} recibidos)"
        )

    points: list[tuple[float, float]] = []
    for index, point in enumerate(value):
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise ZoneConfigurationError(f"{name}[{index}]: cada coordenada debe ser [x, y]")
        x = _validate_number(point[0], f"{name}[{index}][0]")
        y = _validate_number(point[1], f"{name}[{index}][1]")
        points.append((x, y))
    return tuple(points)


def _validate_positive_int(value: object, field: str) -> int:
    # bool es subclase de int en Python: se rechaza de forma explícita.
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ZoneConfigurationError(f"{field}: se esperaba un entero positivo, se recibió {value!r}")
    return value


def _validate_number(value: object, field: str) -> float:
    # bool es subclase de int en Python: se rechaza de forma explícita.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ZoneConfigurationError(f"{field}: se esperaba un número real finito, se recibió {type(value).__name__}")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        raise ZoneConfigurationError(f"{field}: el valor está fuera del rango numérico permitido") from None
    if not finite:
        raise ZoneConfigurationError(f"{field}: NaN e Infinity no están permitidos")
    return value


def _cross(a: Sequence[float], b: Sequence[float], c: Sequence[float]) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a: Sequence[float], b: Sequence[float], point: Sequence[float]) -> bool:
    return (
        abs(_cross(a, b, point)) <= 1e-9
        and min(a[0], b[0]) <= point[0] <= max(a[0], b[0])
        and min(a[1], b[1]) <= point[1] <= max(a[1], b[1])
    )
