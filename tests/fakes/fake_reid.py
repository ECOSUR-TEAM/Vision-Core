class FakeReID:
    def __init__(self):
        self.lost_calls = []

    def resolve(self, track_id, embedding, bbox):
        return "person-1"

    def mark_lost(self, person_id, embedding):
        self.lost_calls.append(person_id)
