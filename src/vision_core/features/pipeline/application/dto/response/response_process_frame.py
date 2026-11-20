from dataclasses import dataclass

from vision_core.features.pipeline.application.dto.response.response_pipeline_event import ResponsePipelineEvent
from vision_core.shared.application.dto.resolved_track_payload import ResolvedTrackPayload


@dataclass(frozen=True, slots=True)
class ResponseProcessFrame:
    people: tuple[ResolvedTrackPayload, ...]
    events: tuple[ResponsePipelineEvent, ...]
    processing_ms: float
