"""Configuración tipada y validada del kernel compartido (ADR 0008)."""

from .persistence import PersistenceSettings
from .settings_config import Settings
from .settings_error import SettingsError
from .settings_helpers import (
    apply_ffmpeg_capture_options,
    environment_with_relay_camera,
    redact_sensitive,
)
from .settings_model_registry import DEFAULT_MODEL_REGISTRY_FILE, ModelRegistrySettings

__all__ = [
    "Settings",
    "SettingsError",
    "PersistenceSettings",
    "ModelRegistrySettings",
    "DEFAULT_MODEL_REGISTRY_FILE",
    "apply_ffmpeg_capture_options",
    "environment_with_relay_camera",
    "redact_sensitive",
]
