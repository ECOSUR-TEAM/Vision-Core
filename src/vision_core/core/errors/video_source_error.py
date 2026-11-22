"""Fallo al abrir, leer o reconectar una fuente de video."""

from vision_core.core.errors.codes import VIDEO_SOURCE_UNAVAILABLE
from vision_core.core.errors.vision_core_error import VisionCoreError


class VideoSourceError(VisionCoreError, ConnectionError):
    default_code = VIDEO_SOURCE_UNAVAILABLE
    default_message = "No se pudo acceder a la fuente de video."
    default_retryable = True
