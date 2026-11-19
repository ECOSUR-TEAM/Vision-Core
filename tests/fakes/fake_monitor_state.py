class FakeMonitorState:
    def __init__(self):
        self.published = []
        self.events = []
        self.status = "starting"

    def set_status(self, status, error=None):
        self.status = status

    def event(self, event):
        self.events.append(event)

    def person_label(self, person_id):
        return f"Persona {person_id}"

    def publish(self, jpeg, people, processing_ms, dropped=0):
        self.published.append((jpeg, people, processing_ms, dropped))

    def current_frame(self):
        return b"jpeg", 4

    def next_frame(self, after):
        return b"next", after + 1

    def snapshot(self):
        return {
            "status": "running",
            "error": None,
            "demo_zones": False,
            "frame": 4,
            "updated_at": 10.0,
            "age_seconds": 0.1,
            "people": [],
            "events": [],
            "counts": {},
            "processing_ms": 2.0,
            "fps": 15.0,
            "dropped_frames": 0,
        }
