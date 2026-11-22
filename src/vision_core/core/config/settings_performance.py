from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PerformanceSettings:
    interval_seconds: float
