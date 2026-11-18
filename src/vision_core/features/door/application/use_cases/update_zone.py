from vision_core.features.door.application.dto.request.request_update import RequestUpdate
from vision_core.features.door.application.dto.response.response_update import ResponseUpdate
from vision_core.features.door.application.mappers.door_mapper import event_to_dto
from vision_core.features.door.domain.ports.door_analytics import DoorAnalytics


class UpdateZone:
    def __init__(self, analytics: DoorAnalytics) -> None:
        self._analytics = analytics

    def execute(self, request: RequestUpdate) -> ResponseUpdate:
        event = self._analytics.update(request.person_id, request.position)
        return ResponseUpdate(event_to_dto(event))
