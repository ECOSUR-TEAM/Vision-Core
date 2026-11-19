from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MonitorSettings:
    host: str
    port: int
    exit_on_error: bool
    minimum_free_disk_mb: int
    disk_check_path: str
