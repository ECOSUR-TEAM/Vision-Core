from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ReIDSettings:
    model_name: str
    weights_profile: str
    weights_path: Path | None
    device: str | None
    threshold: float
    ambiguity_margin: float
    ttl_seconds: float
    gallery_size: int
