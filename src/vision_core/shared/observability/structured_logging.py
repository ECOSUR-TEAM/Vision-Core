import json
import logging
from collections.abc import Mapping
from datetime import datetime, timezone

from vision_core.settings import redact_sensitive
from vision_core.shared.observability.redacted_text_formatter import RedactedTextFormatter


class StructuredJsonFormatter(logging.Formatter):
    def __init__(self, camera_id: str = "default", model_identity: Mapping[str, str] | None = None) -> None:
        super().__init__()
        self.camera_id = camera_id
        self.model_identity = dict(model_identity or {})

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": "vision-core",
            "camera_id": getattr(record, "camera_id", self.camera_id),
            "event_id": getattr(record, "event_id", None),
            "person_id": getattr(record, "person_id", None),
            "duration_ms": getattr(record, "duration_ms", None),
            "error_code": getattr(record, "error_code", None),
            "message": redact_sensitive(record.getMessage()),
        }
        for key, value in self.model_identity.items():
            payload[key] = getattr(record, key, value)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_structured_logging(
    level: str,
    json_format: bool,
    camera_id: str,
    model_identity: Mapping[str, str] | None = None,
) -> None:
    root = logging.getLogger()
    root.setLevel(getattr(logging, level, logging.INFO))
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()
    handler = logging.StreamHandler()
    if json_format:
        handler.setFormatter(StructuredJsonFormatter(camera_id, model_identity))
    else:
        identity = "".join(f" {key}={value}" for key, value in (model_identity or {}).items())
        handler.setFormatter(
            RedactedTextFormatter(
                "%(asctime)s %(levelname)s service=vision-core camera_id=" + camera_id + identity + " %(message)s"
            )
        )
    root.addHandler(handler)
