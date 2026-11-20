"""Contratos versionados compartidos entre features."""

from vision_core.shared.events.schema import EVENT_SCHEMA_VERSION, with_schema_version

__all__ = ["EVENT_SCHEMA_VERSION", "with_schema_version"]
