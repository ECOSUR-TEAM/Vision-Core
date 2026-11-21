from pathlib import Path
from typing import cast

from vision_core.model_registry.active_models import ActiveModels
from vision_core.model_registry.checksum import compute_file_checksum
from vision_core.model_registry.model_descriptor import ModelDescriptor
from vision_core.model_registry.model_registry import ModelRegistry
from vision_core.model_registry.registry_loader import load_model_registry
from vision_core.settings import Settings
from vision_core.shared.errors import ConfigurationError


def resolve_active_models(settings: Settings, *, registry: ModelRegistry | None = None) -> ActiveModels:
    if registry is None:
        registry = load_model_registry(_resolve_registry_path(settings))
    detection = registry.resolve(
        settings.models.detection_model_id,
        task="detection",
        selector=settings.detection.model_path.name,
    )
    embedding = registry.resolve(
        settings.models.embedding_model_id,
        task="embedding",
        selector=settings.reid.model_name,
    )
    _validate_detection_config(detection, settings)
    _validate_embedding_config(embedding, settings)
    if settings.models.verify_checksums:
        _verify_checksum(detection, settings.detection.model_path)
        if settings.reid.weights_path is not None:
            _verify_checksum(embedding, settings.reid.weights_path)
    return ActiveModels(detection=detection, embedding=embedding)


def _resolve_registry_path(settings: Settings) -> Path:
    path = Path(settings.models.registry_file).expanduser()
    if path.is_absolute() or path.is_file():
        return path
    fallback = Path(__file__).resolve().parents[3] / path
    return fallback if fallback.is_file() else path


def _validate_detection_config(model: ModelDescriptor, settings: Settings) -> None:
    expected_confidence = cast(float, model.expected_config["confidence"])
    expected_classes = cast(tuple[int, ...], model.expected_config["classes"])
    if settings.detection.confidence != expected_confidence:
        raise ConfigurationError(
            f"VISION_CORE_DETECTION_CONFIDENCE debe ser {expected_confidence} para el modelo '{model.id}'.",
            context={"variable": "VISION_CORE_DETECTION_CONFIDENCE"},
        )
    if settings.detection.classes != expected_classes:
        expected = ",".join(map(str, expected_classes))
        raise ConfigurationError(
            f"VISION_CORE_DETECTION_CLASSES debe ser {expected} para el modelo '{model.id}'.",
            context={"variable": "VISION_CORE_DETECTION_CLASSES"},
        )


def _validate_embedding_config(model: ModelDescriptor, settings: Settings) -> None:
    expected_weights = cast(str, model.expected_config["weights"])
    if settings.reid.weights_profile != expected_weights:
        raise ConfigurationError(
            f"VISION_CORE_EMBEDDING_WEIGHTS debe ser '{expected_weights}' para el modelo '{model.id}'.",
            context={"variable": "VISION_CORE_EMBEDDING_WEIGHTS"},
        )


def _verify_checksum(model: ModelDescriptor, path: str | Path) -> None:
    if model.checksum_value is None:
        return
    source = Path(path)
    if not source.is_file():
        return
    actual = compute_file_checksum(source, model.checksum_algorithm)
    if actual != model.checksum_value:
        raise ConfigurationError(
            f"El checksum del modelo '{model.id}' no coincide con el registro; revise la versión de los pesos.",
            context={"variable": "MODEL_CHECKSUM"},
        )
