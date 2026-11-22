import logging

from vision_core.core.config import redact_sensitive


class RedactedTextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        message = redact_sensitive(record.getMessage())
        return super().format(logging.makeLogRecord({**record.__dict__, "msg": message, "args": ()}))
