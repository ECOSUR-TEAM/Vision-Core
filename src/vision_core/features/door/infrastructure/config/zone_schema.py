"""Carga segura y validación estricta del esquema del JSON de zonas.

Este módulo se interpone antes de las validaciones geométricas: garantiza que
los datos base sean correctos sin modificar los algoritmos de área, cruce de
segmentos o ``ray casting``.
"""

import json
import math
from pathlib import Path
from typing import Any

from vision_core.shared.errors import ZoneConfigurationError

SUPPORTED_SCHEMA_VERSION = "1.0"
MAX_CONFIG_FILE_BYTES = 100 * 1024
MAX_ZONE_POINTS = 100
REQUIRED_KEYS = ("version", "frame_size", "door", "exterior", "interior")
ZONE_NAMES = ("door", "exterior", "interior")


def load_validated_zone_document(path: str | Path) -> dict[str, Any]:
    """Lee, parsea y valida el documento de zonas antes de cualquier geometría."""
    source = Path(path)
    try:
        size = source.stat().st_size
    except OSError as exc:
        raise ZoneConfigurationError(f"no se puede acceder al archivo de zonas '{source}': {exc}") from None

    if size > MAX_CONFIG_FILE_BYTES:
        raise ZoneConfigurationError(
            f"el archivo de zonas '{source}' supera el límite de {MAX_CONFIG_FILE_BYTES} bytes " f"(tiene {size} bytes)"
        )

    try:
        raw = source.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ZoneConfigurationError(f"no se puede leer '{source}' como UTF-8: {exc}") from None

    try:
        data = json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
    except json.JSONDecodeError as exc:
        raise ZoneConfigurationError(
            f"JSON malformado en '{source}' (línea {exc.lineno}, columna {exc.colno}): {exc.msg}"
        ) from None

    return validate_zone_document(data)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Rechazar claves JSON repetidas en lugar de quedarse con la última."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ZoneConfigurationError(f"clave duplicada no permitida: {key}")
        result[key] = value
    return result


def validate_zone_document(data: object) -> dict[str, Any]:
    """Valida claves, versión, tipos y límites; devuelve datos normalizados."""
    try:
        return _validate_document(data)
    except ZoneConfigurationError:
        raise
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ZoneConfigurationError(f"configuración de zonas inválida: {exc}") from None


def _validate_document(data: object) -> dict[str, Any]:
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
    missing = [key for key in REQUIRED_KEYS if key not in data]
    if missing:
        raise ZoneConfigurationError(f"faltan claves requeridas: {', '.join(missing)}")

    unknown = sorted(str(key) for key in data if key not in REQUIRED_KEYS)
    if unknown:
        raise ZoneConfigurationError(f"claves desconocidas no permitidas: {', '.join(unknown)}")


def _validate_version(value: object) -> str:
    if not isinstance(value, str):
        raise ZoneConfigurationError(
            f"version: se esperaba la cadena '{SUPPORTED_SCHEMA_VERSION}', se recibió {type(value).__name__}"
        )
    if value != SUPPORTED_SCHEMA_VERSION:
        raise ZoneConfigurationError(f"version: esquema '{value}' no soportado; se espera '{SUPPORTED_SCHEMA_VERSION}'")
    return value


def _validate_frame_size(value: object) -> tuple[int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ZoneConfigurationError("frame_size: debe ser una lista o tupla de exactamente 2 enteros positivos")

    width = _validate_positive_int(value[0], "frame_size[0]")
    height = _validate_positive_int(value[1], "frame_size[1]")
    return width, height


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
