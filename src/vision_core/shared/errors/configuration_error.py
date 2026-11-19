"""Fallo de configuración de la aplicación."""

from vision_core.shared.errors.codes import CONFIGURATION_INVALID
from vision_core.shared.errors.vision_core_error import VisionCoreError


class ConfigurationError(VisionCoreError, ValueError):
    default_code = CONFIGURATION_INVALID
    default_message = "La configuración del sistema no es válida."
    default_retryable = False
