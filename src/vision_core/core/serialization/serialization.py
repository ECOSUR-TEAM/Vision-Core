"""Explicit JSON serialization for transport DTOs.

Binary fields (``bytes``) are transport-only: :func:`to_json_value` replaces
them with ``None``, so the field appears as ``null`` and never carries binary
data. The monitor handler serves frames as ``image/jpeg`` and uses
:func:`dumps_json` only for JSON endpoints. Non-finite floats are rejected with
context instead of surfacing as a bare ``ValueError`` from ``json.dumps``.
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
    if type(value).__module__.startswith("numpy"):
        if hasattr(value, "tolist"):
            return to_json_value(value.tolist())
        if hasattr(value, "item"):
            return to_json_value(value.item())
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
