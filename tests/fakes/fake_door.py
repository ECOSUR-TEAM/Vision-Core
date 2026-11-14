from domain.model.event import Event


class FakeDoor:
    def update(self, person_id, position):
        return Event(event="PERSON_ENTERED", person_id=person_id)
