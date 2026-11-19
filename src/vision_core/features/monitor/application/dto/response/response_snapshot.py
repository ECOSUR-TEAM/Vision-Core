from dataclasses import dataclass

from vision_core.shared.application.dto.event_payload import EventPayload
from vision_core.shared.application.dto.monitor_person_payload import MonitorPersonPayload


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
    counts: dict[str, int]
    processing_ms: float
    fps: float
    dropped_frames: int
