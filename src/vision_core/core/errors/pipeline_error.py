"""Fallo durante la orquestación del pipeline de visión."""

from vision_core.core.errors.codes import PIPELINE_FAILED
from vision_core.core.errors.vision_core_error import VisionCoreError


class PipelineError(VisionCoreError, RuntimeError):
    default_code = PIPELINE_FAILED
    default_message = "El pipeline de visión no pudo completar el procesamiento."
    default_retryable = False
