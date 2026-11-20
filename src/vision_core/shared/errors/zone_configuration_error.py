"""Fallo en la configuración o geometría de zonas."""

from vision_core.shared.errors.codes import ZONE_CONFIG_INVALID
from vision_core.shared.errors.vision_core_error import VisionCoreError


class ZoneConfigurationError(VisionCoreError, ValueError):
    default_code = ZONE_CONFIG_INVALID
    default_message = "La configuración de zonas no es válida."
    default_retryable = False
