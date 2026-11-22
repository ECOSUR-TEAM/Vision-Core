"""Payloads de transporte compartidos por varios slices (ADR 0008)."""

from vision_core.core.dto.bbox_payload import BBoxPayload
from vision_core.core.dto.detection_payload import DetectionPayload
from vision_core.core.dto.event_payload import EventPayload
from vision_core.core.dto.frame_like import FrameLike
from vision_core.core.dto.monitor_person_payload import MonitorPersonPayload
from vision_core.core.dto.observation_payload import ObservationPayload
from vision_core.core.dto.resolved_track_payload import ResolvedTrackPayload
from vision_core.core.serialization.json_value import JSONValue
from vision_core.core.serialization.schema_version import EVENT_SCHEMA_VERSION

__all__ = [
    "EVENT_SCHEMA_VERSION",
    "BBoxPayload",
    "DetectionPayload",
    "EventPayload",
    "FrameLike",
    "JSONValue",
    "MonitorPersonPayload",
    "ObservationPayload",
    "ResolvedTrackPayload",
]
