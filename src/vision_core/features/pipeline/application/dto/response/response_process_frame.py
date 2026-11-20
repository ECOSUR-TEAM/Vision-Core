from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ResponseProcessFrame:
    people: tuple[dict[str, Any], ...]
    events: tuple[dict[str, Any], ...]
    processing_ms: float
