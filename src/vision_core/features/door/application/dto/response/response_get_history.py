from dataclasses import dataclass

from vision_core.core.dto.observation_payload import ObservationPayload


@dataclass(frozen=True, slots=True)
class ResponseGetHistory:
    observations: tuple[ObservationPayload, ...]
