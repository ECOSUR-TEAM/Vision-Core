"""Shared application contracts for DTO payloads.

These types are shared because detection, door, monitor and pipeline expose the
same transport payloads (bounding boxes, events, observations and tracks) in
more than one slice. They are dataclasses rather than plain dicts so ``frozen``
also protects the nested contract, and they live outside feature DTO folders so
the one-DTO-per-file convention remains intact.
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
