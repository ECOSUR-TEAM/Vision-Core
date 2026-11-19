"""Shared DTO payload contracts.

Only transport payloads shared by several features live here. Request and
response DTOs remain the property of their own feature; see
``docs/architecture.md`` for the justification and the allowed imports.
"""

from vision_core.shared.application.dto.bbox_payload import BBoxPayload
from vision_core.shared.application.dto.detection_payload import DetectionPayload
from vision_core.shared.application.dto.event_payload import EventPayload
from vision_core.shared.application.dto.frame_like import FrameLike
from vision_core.shared.application.dto.json_value import JSONValue
from vision_core.shared.application.dto.monitor_person_payload import MonitorPersonPayload
from vision_core.shared.application.dto.observation_payload import ObservationPayload
from vision_core.shared.application.dto.resolved_track_payload import ResolvedTrackPayload

__all__ = [
    "BBoxPayload",
    "DetectionPayload",
    "EventPayload",
    "FrameLike",
    "JSONValue",
    "MonitorPersonPayload",
    "ObservationPayload",
    "ResolvedTrackPayload",
]
