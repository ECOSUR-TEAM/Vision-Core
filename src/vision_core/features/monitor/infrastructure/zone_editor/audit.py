"""Auditoría ligera de cambios de zonas: usuario, timestamp y hashes."""

import json
import logging
from datetime import UTC, datetime

from vision_core.features.monitor.infrastructure.zone_editor.config import ZoneEditorConfig

_LOGGER = logging.getLogger(__name__)


class ZoneAudit:
    def __init__(self, config: ZoneEditorConfig):
        self._file = config.audit_file

    def record(self, user: str, previous_hash: str, new_hash: str, *, timestamp: str | None = None) -> dict[str, str]:
        entry = {
            "user": user,
            "timestamp": timestamp or datetime.now(UTC).isoformat(),
            "previous_sha256": previous_hash,
            "new_sha256": new_hash,
        }
        if self._file is not None:
            self._file.parent.mkdir(parents=True, exist_ok=True)
            with self._file.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(entry, ensure_ascii=False) + "\n")
        _LOGGER.info("zone_editor_audit user=%s previous_sha256=%s new_sha256=%s", user, previous_hash, new_hash)
        return entry
