from dataclasses import dataclass

from vision_core.core.dto.resolved_track_payload import ResolvedTrackPayload
from vision_core.features.pipeline.application.dto.response.response_pipeline_event import ResponsePipelineEvent


@dataclass(frozen=True, slots=True)
class ResponseProcessFrame:
    people: tuple[ResolvedTrackPayload, ...]
    events: tuple[ResponsePipelineEvent, ...]
    processing_ms: float
