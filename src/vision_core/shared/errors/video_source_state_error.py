"""Uso inválido del ciclo de vida de una fuente de video."""

from vision_core.shared.errors.codes import VIDEO_SOURCE_STATE
from vision_core.shared.errors.vision_core_error import VisionCoreError


class VideoSourceStateError(VisionCoreError, RuntimeError):
    default_code = VIDEO_SOURCE_STATE
    default_message = "La fuente de video no está en el estado esperado."
    default_retryable = False
