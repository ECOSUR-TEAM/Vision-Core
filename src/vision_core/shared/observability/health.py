import shutil
from collections.abc import Mapping


class HealthStatus:
    """Readiness checks kept separate from liveness."""

    def __init__(
        self,
        minimum_free_disk_mb: int = 500,
        disk_path: str = ".",
        model_metadata: Mapping[str, Mapping[str, str]] | None = None,
    ) -> None:
        self.minimum_free_disk_mb = minimum_free_disk_mb
        self.disk_path = disk_path
        self.config_valid = True
        self.model_loaded = False
        self.source_connected = False
        self.model_metadata = {role: dict(values) for role, values in (model_metadata or {}).items()}

    def set_ready(self, *, config_valid=None, model_loaded=None, source_connected=None) -> None:
        if config_valid is not None:
            self.config_valid = config_valid
        if model_loaded is not None:
            self.model_loaded = model_loaded
        if source_connected is not None:
            self.source_connected = source_connected

    def set_model_metadata(self, model_metadata: Mapping[str, Mapping[str, str]]) -> None:
        self.model_metadata = {role: dict(values) for role, values in model_metadata.items()}

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
        payload = {
            "ready": all(checks.values()),
            "checks": checks,
            "disk_free_mb": round(free_mb, 2),
            "minimum_free_disk_mb": self.minimum_free_disk_mb,
        }
        if self.model_metadata:
            detection = self.model_metadata.get("detection", {})
            payload["models"] = {role: dict(values) for role, values in self.model_metadata.items()}
            payload["model_id"] = detection.get("model_id")
            payload["model_version"] = detection.get("model_version")
            payload["model_hash"] = detection.get("model_hash")
        return payload
