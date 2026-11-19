from vision_core.features.door.application.dto.request.request_get_history import RequestGetHistory
from vision_core.features.door.application.dto.request.request_update import RequestUpdate
from vision_core.features.door.application.use_cases.get_history import GetHistory
from vision_core.features.door.application.use_cases.update_zone import UpdateZone
from vision_core.features.door.domain.entities.zone_observation import ZoneObservation
from vision_core.features.door.domain.ports.door_analytics import DoorAnalytics
from vision_core.shared.application.dto import EventPayload, ObservationPayload
from vision_core.shared.domain.event import Event
from vision_core.shared.events import EVENT_SCHEMA_VERSION


class FakeDoorAnalytics(DoorAnalytics):
    def __init__(self):
        self.updated = []

    def update(self, person_id, position):
        self.updated.append((person_id, position))
        return Event("PERSON_ENTERED", person_id, timestamp=10, metadata={"to_zone": "interior"})

    def get_history(self, person_id):
        return (ZoneObservation((1.0, 2.0), "exterior", 10.0),)


def test_update_zone_maps_event_without_camera_or_adapter():
    analytics = FakeDoorAnalytics()

    response = UpdateZone(analytics).execute(RequestUpdate("person-1", (1.0, 2.0)))

    assert analytics.updated == [("person-1", (1.0, 2.0))]
    assert response.event == EventPayload(
        event="PERSON_ENTERED",
        person_id="person-1",
        timestamp=10.0,
        metadata={"to_zone": "interior"},
        schema_version=EVENT_SCHEMA_VERSION,
    )


def test_get_history_maps_observations():
    response = GetHistory(FakeDoorAnalytics()).execute(RequestGetHistory("person-1"))

    assert response.observations == (ObservationPayload((1.0, 2.0), "exterior", 10.0),)
