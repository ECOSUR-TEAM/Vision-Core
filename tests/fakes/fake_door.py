from vision_core.features.door.domain.ports.door_analytics import DoorAnalytics
from vision_core.shared.domain.event import Event


class FakeDoor(DoorAnalytics):
    def update(self, person_id, position):
        return Event(event="PERSON_ENTERED", person_id=person_id)

    def get_history(self, person_id):
        return ()
