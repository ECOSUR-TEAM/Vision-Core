from dataclasses import dataclass
from pathlib import Path

DEFAULT_MODEL_REGISTRY_FILE = Path(__file__).resolve().parents[3] / "config" / "models.yml"


@dataclass(frozen=True, slots=True)
class ModelRegistrySettings:
    registry_file: Path
    detection_model_id: str
    embedding_model_id: str
    verify_checksums: bool
