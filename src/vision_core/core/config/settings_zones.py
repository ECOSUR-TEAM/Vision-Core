from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ZonesSettings:
    zones_file: Path | None
    confirmation_frames: int
    demo_zones: bool
    uncalibrated: bool
    editor_enabled: bool = False
    editor_token: str | None = None
    editor_audit_file: Path | None = None
