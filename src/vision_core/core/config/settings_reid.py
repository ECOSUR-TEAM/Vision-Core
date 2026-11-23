from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReIDSettings:
    model_name: str
    weights_profile: str
    device: str | None
    precision: str
    threshold: float
    ambiguity_margin: float
    ttl_seconds: float
    gallery_size: int
