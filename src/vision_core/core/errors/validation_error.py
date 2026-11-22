"""Fallo de validación de entradas en un límite del sistema."""

from vision_core.core.errors.codes import VALIDATION_FAILED
from vision_core.core.errors.vision_core_error import VisionCoreError


class ValidationError(VisionCoreError, ValueError):
    default_code = VALIDATION_FAILED
    default_message = "Los datos recibidos no son válidos."
    default_retryable = False
