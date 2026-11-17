"""Unique visitors and current occupancy are different from crossing counts."""
from domain.model.event import Event


class SessionAttendance:
    def __init__(self):
        self.visitors: set[str] = set()
        self.inside: set[str] = set()

    def apply(self, event: Event) -> dict:
        returning = False
        if event.event == 'PERSON_ENTERED':
            returning = event.person_id in self.visitors
            self.visitors.add(event.person_id)
            self.inside.add(event.person_id)
        elif event.event == 'PERSON_EXITED':
            self.inside.discard(event.person_id)
        return {'returning_person': returning,
                'unique_people_entered': len(self.visitors),
                'people_inside': len(self.inside)}
