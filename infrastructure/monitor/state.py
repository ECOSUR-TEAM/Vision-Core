"""In-memory monitor telemetry and synchronization."""
import threading
import time
from collections import Counter, deque


class MonitorState:
    def __init__(self, demo=False):
        self.lock = threading.Lock()
        self.changed = threading.Condition(self.lock)
        self._person_numbers = {}
        self.status = 'starting'
        self.error = None
        self.demo = demo
        self.jpeg = None
        self.updated = None
        self.previous = None
        self.sequence = 0
        self.people = []
        self.events = deque(maxlen=100)
        self.counts = Counter()
        self.processing_ms = 0.
        self.fps = 0.
        self.dropped = 0

    def set_status(self, status, error=None):
        with self.lock:
            self.status, self.error = status, error

    def event(self, event):
        with self.lock:
            self.events.appendleft(event.to_dict())
            self.counts[event.event] += 1

    def person_label(self, person_id):
        with self.lock:
            number = self._person_numbers.setdefault(
                person_id, len(self._person_numbers) + 1
            )
            return f'Persona {number}'

    def publish(self, jpeg, people, processing_ms, dropped=0):
        now = time.monotonic()
        with self.lock:
            if self.previous is not None:
                current = 1 / max(now - self.previous, .000001)
                self.fps = current if not self.fps else .8*self.fps + .2*current
            self.previous = now
            self.updated = time.time()
            self.sequence += 1
            self.jpeg = jpeg
            self.people = people
            self.processing_ms = processing_ms
            self.dropped = dropped
            self.status = 'running'
            self.changed.notify_all()

    def next_frame(self, after):
        """Wait for a fresh image; slow viewers skip old frames instead of queueing."""
        with self.changed:
            self.changed.wait_for(lambda: self.sequence > after, timeout=1)
            if self.sequence <= after or self.jpeg is None:
                return None, self.sequence
            return self.jpeg, self.sequence

    def snapshot(self):
        with self.lock:
            age = time.time()-self.updated if self.updated is not None else None
            status = 'stale' if self.status == 'running' and age > 5 else self.status
            return {'status': status, 'error': self.error, 'demo_zones': self.demo,
                    'frame': self.sequence, 'updated_at': self.updated, 'age_seconds': age,
                    'people': self.people if status == 'running' else [],
                    'events': list(self.events), 'counts': dict(self.counts),
                    'processing_ms': self.processing_ms, 'fps': self.fps,
                    'dropped_frames': self.dropped}
