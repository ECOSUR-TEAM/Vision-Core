import shutil


class HealthStatus:
    """Readiness checks kept separate from liveness."""

    def __init__(self, minimum_free_disk_mb: int = 500, disk_path: str = ".") -> None:
        self.minimum_free_disk_mb = minimum_free_disk_mb
        self.disk_path = disk_path
        self.config_valid = True
        self.model_loaded = False
        self.source_connected = False

    def set_ready(self, *, config_valid=None, model_loaded=None, source_connected=None) -> None:
        if config_valid is not None:
            self.config_valid = config_valid
        if model_loaded is not None:
            self.model_loaded = model_loaded
        if source_connected is not None:
            self.source_connected = source_connected

    def snapshot(self) -> dict:
        try:
            usage = shutil.disk_usage(self.disk_path)
            free_mb = usage.free / (1024 * 1024)
            disk_ok = free_mb >= self.minimum_free_disk_mb
        except OSError:
            free_mb = 0
            disk_ok = False
        checks = {
            "configuration": self.config_valid,
            "model": self.model_loaded,
            "video_source": self.source_connected,
            "disk": disk_ok,
        }
        return {
            "ready": all(checks.values()),
            "checks": checks,
            "disk_free_mb": round(free_mb, 2),
            "minimum_free_disk_mb": self.minimum_free_disk_mb,
        }
