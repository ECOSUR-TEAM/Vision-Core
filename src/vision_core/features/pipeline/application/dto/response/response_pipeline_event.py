from collections.abc import Mapping
from dataclasses import dataclass

from vision_core.core.dto import EVENT_SCHEMA_VERSION, JSONValue


@dataclass(frozen=True, slots=True)
class ResponsePipelineEvent:
    event: str
    person_id: str
    timestamp: float
    metadata: Mapping[str, JSONValue]
    schema_version: str = EVENT_SCHEMA_VERSION
