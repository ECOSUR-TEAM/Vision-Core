from dataclasses import dataclass

from vision_core.shared.application.dto.observation_payload import ObservationPayload


@dataclass(frozen=True, slots=True)
class ResponseGetHistory:
    observations: tuple[ObservationPayload, ...]
