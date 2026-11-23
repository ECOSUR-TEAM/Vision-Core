"""Editor de zonas: configuración explícita detrás de una marca de activación."""

from dataclasses import dataclass
from pathlib import Path

from vision_core.core.validation.zone_payload import MAX_ZONE_PAYLOAD_BYTES, SUPPORTED_ZONE_SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class ZoneEditorConfig:
    enabled: bool = False
    zones_file: Path | None = None
    editor_token: str | None = None
    audit_file: Path | None = None
    max_payload_bytes: int = MAX_ZONE_PAYLOAD_BYTES
    schema_version: str = SUPPORTED_ZONE_SCHEMA_VERSION

    @property
    def available(self) -> bool:
        return self.enabled and self.zones_file is not None
