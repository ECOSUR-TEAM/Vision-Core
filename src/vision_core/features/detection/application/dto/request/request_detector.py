from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RequestDetector:
    """Input frame for a detection operation."""

    frame: Any
