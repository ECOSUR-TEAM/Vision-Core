"""Serialización JSON explícita y contratos de eventos versionados (ADR 0008)."""

from vision_core.core.serialization.json_value import JSONValue
from vision_core.core.serialization.schema import with_schema_version
from vision_core.core.serialization.schema_version import EVENT_SCHEMA_VERSION
from vision_core.core.serialization.serialization import dumps_json, to_json_value

__all__ = [
    "EVENT_SCHEMA_VERSION",
    "JSONValue",
    "dumps_json",
    "to_json_value",
    "with_schema_version",
]
