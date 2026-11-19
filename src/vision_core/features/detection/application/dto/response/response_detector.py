from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResponseDetector:
    """Serializable detection results."""

    detections: tuple[dict[str, object], ...]
