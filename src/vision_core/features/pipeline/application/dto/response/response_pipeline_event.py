from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ResponsePipelineEvent:
    event: str
    person_id: str
    timestamp: float
    metadata: dict[str, Any]
