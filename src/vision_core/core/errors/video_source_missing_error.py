"""Archivo de video configurado ausente o ilegible."""

from vision_core.core.errors.codes import VIDEO_SOURCE_MISSING
from vision_core.core.errors.vision_core_error import VisionCoreError


class VideoSourceMissingError(VisionCoreError, FileNotFoundError):
    default_code = VIDEO_SOURCE_MISSING
    default_message = "El archivo de video configurado no está disponible."
    default_retryable = False
