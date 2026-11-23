from collections.abc import Mapping
from dataclasses import dataclass

from vision_core.core.dto import JSONValue
from vision_core.core.dto.event_payload import EventPayload
from vision_core.core.dto.monitor_person_payload import MonitorPersonPayload
from vision_core.features.monitor.application.dto.response.response_camera_quality import ResponseCameraQuality


@dataclass(frozen=True, slots=True)
class ResponseSnapshot:
    status: str
    error: str | None
    demo_zones: bool
    frame: int
    updated_at: float | None
    age_seconds: float | None
    people: tuple[MonitorPersonPayload, ...]
    events: tuple[EventPayload, ...]
    counts: Mapping[str, int]
    processing_ms: float
    fps: float
    dropped_frames: int
    persistence: Mapping[str, JSONValue] | None
    camera_quality: ResponseCameraQuality
