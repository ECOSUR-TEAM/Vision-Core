"""Modelo de ReID no disponible en el dispositivo solicitado."""

from vision_core.shared.errors.codes import REID_MODEL_UNAVAILABLE
from vision_core.shared.errors.vision_core_error import VisionCoreError


class ReIDModelUnavailableError(VisionCoreError, RuntimeError):
    default_code = REID_MODEL_UNAVAILABLE
    default_message = "El modelo de ReID no está disponible en este dispositivo."
    default_retryable = False
