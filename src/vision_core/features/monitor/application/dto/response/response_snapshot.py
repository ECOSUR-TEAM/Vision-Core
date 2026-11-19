from dataclasses import dataclass


@dataclass(frozen=True)
class ResponseSnapshot:
    status: str
    error: str | None
    demo_zones: bool
    frame: int
    updated_at: float | None
    age_seconds: float | None
    people: tuple[dict[str, object], ...]
    events: tuple[dict[str, object], ...]
    counts: dict[str, int]
    processing_ms: float
    fps: float
    dropped_frames: int
    persistence: dict[str, object] | None = None
