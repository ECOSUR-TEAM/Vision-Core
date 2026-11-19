import json
import logging
from datetime import datetime, timezone

from vision_core.settings import redact_sensitive


class StructuredJsonFormatter(logging.Formatter):
    def __init__(self, camera_id: str = "default") -> None:
        super().__init__()
        self.camera_id = camera_id

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
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_structured_logging(level: str, json_format: bool, camera_id: str) -> None:
    root = logging.getLogger()
    root.setLevel(getattr(logging, level, logging.INFO))
    for handler in root.handlers:
        root.removeHandler(handler)
    handler = logging.StreamHandler()
    if json_format:
        handler.setFormatter(StructuredJsonFormatter(camera_id))
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s service=vision-core camera_id=" + camera_id + " %(message)s")
        )
    root.addHandler(handler)
