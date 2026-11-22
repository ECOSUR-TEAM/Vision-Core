from vision_core.core.domain.event import Event
from vision_core.features.door.domain.ports.door_analytics import DoorAnalytics


class FakeDoor(DoorAnalytics):
    def update(self, person_id, position):
        return Event(event="PERSON_ENTERED", person_id=person_id)

    def get_history(self, person_id):
        return ()
