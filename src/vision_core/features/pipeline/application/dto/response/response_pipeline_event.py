from collections.abc import Mapping
from dataclasses import dataclass

from vision_core.shared.application.dto.json_value import JSONValue


@dataclass(frozen=True, slots=True)
class ResponsePipelineEvent:
    event: str
    person_id: str
    timestamp: float
    metadata: Mapping[str, JSONValue]
