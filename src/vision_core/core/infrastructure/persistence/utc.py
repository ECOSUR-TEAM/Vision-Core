from datetime import datetime, timezone


def utc_text(timestamp: float | None = None) -> str:
    instant = datetime.now(timezone.utc) if timestamp is None else datetime.fromtimestamp(timestamp, tz=timezone.utc)
    return instant.isoformat(timespec="milliseconds").replace("+00:00", "Z")
