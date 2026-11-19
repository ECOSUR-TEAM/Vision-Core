"""Format validation shared by application mappers.

Validation happens at the mapper (the boundary), before values are converted
into domain entities or transport payloads, so invalid input fails close to
the caller instead of deep inside a use case.
"""

import math
from collections.abc import Mapping
from enum import Enum
from typing import Any

from vision_core.shared.application.dto.bbox_payload import BBoxPayload
from vision_core.shared.application.dto.json_value import JSONValue
from vision_core.shared.application.dto.serialization import to_json_value

_BBOX_FIELDS = ("x1", "y1", "x2", "y2")


def finite_float(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a finite number")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field} must be a finite number") from exc
    if not math.isfinite(result):
        raise ValueError(f"{field} must be a finite number")
    return result


def finite_unit_float(value: Any, field: str) -> float:
    result = finite_float(value, field)
    if not 0.0 <= result <= 1.0:
        raise ValueError(f"{field} must be in [0, 1]")
    return result


def bounded_int(value: Any, field: str, *, minimum: int = 0, maximum: int | None = None) -> int:
    if isinstance(value, bool) or (isinstance(value, float) and not value.is_integer()):
        raise ValueError(f"{field} must be an integer")
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field} must be an integer") from exc
    if result < minimum or (maximum is not None and result > maximum):
        raise ValueError(f"{field} is outside the allowed range")
    return result


def required_track_id(value: Any, field: str = "track_id") -> int:
    if value is None:
        raise ValueError(f"{field} is required at the DTO boundary")
    return bounded_int(value, field)


def required_str(value: Any, field: str) -> str:
    if isinstance(value, Enum) and isinstance(value.value, str):
        value = value.value
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value


def finite_bbox(value: Any, field: str = "bbox") -> tuple[float, float, float, float]:
    if isinstance(value, BBoxPayload):
        coordinates = (value.x1, value.y1, value.x2, value.y2)
    elif all(hasattr(value, name) for name in _BBOX_FIELDS):
        coordinates = tuple(finite_float(getattr(value, name), f"{field}.{name}") for name in _BBOX_FIELDS)
    elif isinstance(value, Mapping):
        if any(name not in value for name in _BBOX_FIELDS):
            raise ValueError(f"{field} requires x1, y1, x2 and y2")
        coordinates = tuple(finite_float(value[name], f"{field}.{name}") for name in _BBOX_FIELDS)
    else:
        raise ValueError(f"{field} must be a BBoxPayload or a mapping")
    x1, y1, x2, y2 = coordinates
    if x2 <= x1 or y2 <= y1:
        raise ValueError(f"{field} must have positive area")
    return coordinates


def json_metadata(value: Any, field: str = "metadata") -> dict[str, JSONValue]:
    if value is None:
        return {}
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"{field} must be a mapping with string keys")
    result = to_json_value(dict(value))
    if not isinstance(result, dict):
        raise ValueError(f"{field} must serialize to a JSON object")
    return result
