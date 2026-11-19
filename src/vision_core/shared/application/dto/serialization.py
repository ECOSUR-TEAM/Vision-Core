"""Explicit JSON serialization for transport DTOs.

Binary fields (``bytes``) are transport-only and are omitted from JSON: the
monitor handler serves frames as ``image/jpeg`` and uses :func:`dumps_json`
only for JSON endpoints. Non-finite floats are rejected with context instead
of surfacing as a bare ``ValueError`` from ``json.dumps``.
"""

import json
import math
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any


def to_json_value(value: Any) -> Any:
    if isinstance(value, bytes):
        return None
    if isinstance(value, Enum):
        return to_json_value(value.value)
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: to_json_value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): to_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_json_value(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("DTO contains a non-finite float; JSON output would be invalid")
    return value


def dumps_json(value: Any) -> str:
    return json.dumps(to_json_value(value), allow_nan=False)
