"""Taxonomía de errores estables de Vision Core."""

from vision_core.core.errors.configuration_error import ConfigurationError
from vision_core.core.errors.model_error import ModelError
from vision_core.core.errors.pipeline_error import PipelineError
from vision_core.core.errors.reid_error import ReIDError
from vision_core.core.errors.reid_model_unavailable_error import ReIDModelUnavailableError
from vision_core.core.errors.validation_error import ValidationError
from vision_core.core.errors.video_source_error import VideoSourceError
from vision_core.core.errors.video_source_missing_error import VideoSourceMissingError
from vision_core.core.errors.video_source_state_error import VideoSourceStateError
from vision_core.core.errors.vision_core_error import VisionCoreError
from vision_core.core.errors.zone_configuration_error import ZoneConfigurationError

__all__ = [
    "ConfigurationError",
    "ModelError",
    "PipelineError",
    "ReIDError",
    "ReIDModelUnavailableError",
    "ValidationError",
    "VideoSourceError",
    "VideoSourceMissingError",
    "VideoSourceStateError",
    "VisionCoreError",
    "ZoneConfigurationError",
]
