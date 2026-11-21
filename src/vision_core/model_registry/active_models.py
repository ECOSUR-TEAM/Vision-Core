from dataclasses import dataclass

from vision_core.model_registry.model_descriptor import ModelDescriptor


@dataclass(frozen=True, slots=True)
class ActiveModels:
    detection: ModelDescriptor
    embedding: ModelDescriptor

    def as_log_identity(self) -> dict[str, str]:
        identity = _descriptor_identity(self.detection)
        identity.update({f"embedding_{key}": value for key, value in _descriptor_identity(self.embedding).items()})
        return identity

    def as_health_metadata(self) -> dict[str, dict[str, str]]:
        return {
            "detection": _descriptor_identity(self.detection),
            "embedding": _descriptor_identity(self.embedding),
        }


def _descriptor_identity(model: ModelDescriptor) -> dict[str, str]:
    return {
        "model_id": model.id,
        "model_version": model.version,
        "model_hash": model.model_hash,
    }
