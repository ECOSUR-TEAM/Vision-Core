from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LoggingSettings:
    level: str
    json_format: bool
    camera_id: str
