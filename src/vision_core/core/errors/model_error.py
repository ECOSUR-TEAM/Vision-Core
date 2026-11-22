"""Fallo al cargar o ejecutar un modelo de visión."""

from vision_core.core.errors.codes import MODEL_UNAVAILABLE
from vision_core.core.errors.vision_core_error import VisionCoreError


class ModelError(VisionCoreError, RuntimeError):
    default_code = MODEL_UNAVAILABLE
    default_message = "El modelo de visión no está disponible."
    default_retryable = False
