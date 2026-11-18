from vision_core.features.door.application.dto.request.request_get_history import RequestGetHistory
from vision_core.features.door.application.dto.response.response_get_history import ResponseGetHistory
from vision_core.features.door.application.mappers.door_mapper import observations_to_dto
from vision_core.features.door.domain.ports.door_analytics import DoorAnalytics


class GetHistory:
    def __init__(self, analytics: DoorAnalytics) -> None:
        self._analytics = analytics

    def execute(self, request: RequestGetHistory) -> ResponseGetHistory:
        return ResponseGetHistory(observations_to_dto(
            self._analytics.get_history(request.person_id)))
