from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RequestDetector:
    """Input frame for a detection operation."""

    frame: object
