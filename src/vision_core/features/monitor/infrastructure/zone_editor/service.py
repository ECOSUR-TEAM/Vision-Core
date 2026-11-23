"""Use case del editor de zonas: cargar, validar y guardar con auditoría."""

import hashlib
import json
import logging
import os
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from vision_core.core.errors import VisionCoreError, codes
from vision_core.core.serialization import dumps_json
from vision_core.core.validation.zone_payload import (
    MAX_ZONE_POINTS,
    reject_duplicate_json_keys,
    validate_zone_payload,
    zone_document_to_json,
)
from vision_core.features.monitor.infrastructure.zone_editor.access import can_save_zones, editor_user
from vision_core.features.monitor.infrastructure.zone_editor.audit import ZoneAudit
from vision_core.features.monitor.infrastructure.zone_editor.config import ZoneEditorConfig
from vision_core.features.monitor.infrastructure.zone_editor.storage import (
    ReplaceFunction,
    read_zone_bytes,
    restore_zone_bytes,
    write_zone_bytes,
)

logger = logging.getLogger(__name__)


class ZoneEditorService:
    def __init__(
        self,
        config: ZoneEditorConfig,
        *,
        audit: ZoneAudit | None = None,
        replace: ReplaceFunction | None = None,
    ):
        self.config = config
        self._audit = audit or ZoneAudit(config)
        self._replace: ReplaceFunction = replace or os.replace
        self._lock = threading.RLock()

    @classmethod
    def disabled(cls) -> "ZoneEditorService":
        return cls(ZoneEditorConfig())

    def describe(self, headers: Mapping[str, str]) -> dict[str, Any]:
        return {
            "enabled": self.config.available,
            "can_save": can_save_zones(self.config, headers),
            "schema_version": self.config.schema_version,
            "max_payload_bytes": self.config.max_payload_bytes,
            "max_zone_points": MAX_ZONE_POINTS,
        }

    def load(self) -> dict[str, Any]:
        self._require_editor()
        assert self.config.zones_file is not None
        raw = read_zone_bytes(self.config.zones_file, max_bytes=self.config.max_payload_bytes)
        try:
            document = json.loads(raw.decode("utf-8"), object_pairs_hook=reject_duplicate_json_keys)
        except (UnicodeError, json.JSONDecodeError) as error:
            raise VisionCoreError(
                "El archivo de zonas no contiene JSON válido.",
                code=codes.ZONE_CONFIG_INVALID,
                retryable=False,
            ) from error
        return zone_document_to_json(validate_zone_payload(document, max_bytes=self.config.max_payload_bytes))

    def validate(self, document: object) -> dict[str, Any]:
        self._require_editor()
        return zone_document_to_json(validate_zone_payload(document, max_bytes=self.config.max_payload_bytes))

    def save(self, document: object, headers: Mapping[str, str]) -> dict[str, Any]:
        self._require_editor()
        if not can_save_zones(self.config, headers):
            logger.warning("zone_editor_access_denied user=%s", editor_user(headers))
            raise VisionCoreError(
                "No tienes permiso para guardar zonas.",
                code=codes.ZONE_EDITOR_FORBIDDEN,
                retryable=False,
            )
        with self._lock:
            validated = validate_zone_payload(document, max_bytes=self.config.max_payload_bytes)
            zones = zone_document_to_json(validated)
            payload = dumps_json(zones).encode("utf-8")
            new_hash = hashlib.sha256(payload).hexdigest()

            assert self.config.zones_file is not None
            path: Path = self.config.zones_file
            previous = path.read_bytes() if path.is_file() else None
            previous_hash = hashlib.sha256(previous).hexdigest() if previous is not None else ""
            try:
                write_zone_bytes(path, payload, replace=self._replace)
                audit_entry = self._audit.record(editor_user(headers), previous_hash, new_hash)
            except Exception:
                restore_zone_bytes(path, previous, replace=self._replace)
                raise
        return {"zones": zones, "audit": audit_entry, "restart_required": True}

    def _require_editor(self) -> None:
        if not self.config.available:
            raise VisionCoreError(
                "El editor de zonas no está disponible.",
                code=codes.REQUEST_NOT_FOUND,
                retryable=False,
            )
