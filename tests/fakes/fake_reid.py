class FakeReID:
    def __init__(self):
        self.lost_calls = []
        self.visible_tracks = set()

    def begin_frame(self, visible_track_ids):
        self.visible_tracks = set(visible_track_ids)

    def resolve(self, track_id, embedding, bbox):
        return "person-1"

    def mark_lost(self, person_id, embedding):
        self.lost_calls.append(person_id)
