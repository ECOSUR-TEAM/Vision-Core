from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DetectionSettings:
    model_path: Path
    device: str | None
    precision: str
    confidence: float
    classes: tuple[int, ...]
    tracking_enabled: bool
    max_missed_frames: int
