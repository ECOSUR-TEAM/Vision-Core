import json
from dataclasses import asdict
from enum import Enum
from typing import Any

import numpy as np

from vision_core.features.pipeline.application.dto.response.response_pipeline_event import ResponsePipelineEvent
from vision_core.features.pipeline.domain.entities.resolved_track import ResolvedTrack
from vision_core.shared.domain.event import Event

__all__ = [
    "event_to_dict",
    "event_to_dto",
    "event_to_json",
    "resolved_track_to_dto",
]


def _jsonable(value: Any) -> Any:
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


def event_to_dto(event: Event) -> ResponsePipelineEvent:
    return ResponsePipelineEvent(
        event=event.event,
        person_id=event.person_id,
        timestamp=event.timestamp,
        metadata=_jsonable(event.metadata),
    )


def event_to_dict(event: Event) -> dict[str, Any]:
    return asdict(event_to_dto(event))


def event_to_json(event: Event) -> str:
    return json.dumps(event_to_dict(event), allow_nan=False)


def resolved_track_to_dto(track: ResolvedTrack) -> dict[str, Any]:
    return asdict(track)
