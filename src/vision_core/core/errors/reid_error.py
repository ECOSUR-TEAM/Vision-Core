"""Fallo en la memoria o extracción de identidades ReID."""

from vision_core.core.errors.codes import REID_MODEL_INVALID
from vision_core.core.errors.vision_core_error import VisionCoreError


class ReIDError(VisionCoreError, ValueError):
    default_code = REID_MODEL_INVALID
    default_message = "La memoria de identidades no está disponible."
    default_retryable = False
