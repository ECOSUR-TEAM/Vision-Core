from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class QualityObservation:
    status: str
    reason: str | None
    signals: Mapping[str, bool]
    width: int
    height: int
    brightness: float
    blur_variance: float

    @classmethod
    def healthy(cls, width: int, height: int, brightness: float, blur_variance: float) -> "QualityObservation":
        return cls(
            status="ok",
            reason=None,
            signals=MappingProxyType({}),
            width=width,
            height=height,
            brightness=brightness,
            blur_variance=blur_variance,
        )
