"""Serialize domain events at the application boundary."""
import json
from enum import Enum
from typing import Any

import numpy as np

from domain.model.event import Event


def _jsonable(value: Any) -> Any:
    """Convert event metadata to values supported by the JSON encoder."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def event_to_dict(event: Event) -> dict[str, Any]:
    return {
        "event": event.event,
        "person_id": event.person_id,
        "timestamp": event.timestamp,
        "metadata": _jsonable(event.metadata),
    }


def event_to_json(event: Event) -> str:
    return json.dumps(event_to_dict(event))
