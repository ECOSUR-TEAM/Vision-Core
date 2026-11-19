"""In-memory monitor telemetry and synchronization."""

import logging
import threading
import time
from collections import Counter, deque

from vision_core.shared.observability.health import HealthStatus
from vision_core.shared.observability.metrics import ObservabilityMetrics

logger = logging.getLogger(__name__)


def _event_to_dict(event):
    return {
        "event": event.event,
        "person_id": event.person_id,
        "timestamp": event.timestamp,
        "metadata": dict(event.metadata),
    }


class MonitorState:
    def __init__(
        self,
        demo=False,
        event_serializer=None,
        metrics=None,
        health=None,
    ):
        self._event_serializer = event_serializer or _event_to_dict
        self.lock = threading.Lock()
        self.changed = threading.Condition(self.lock)
        self._person_numbers = {}
        self.status = "starting"
        self.error = None
        self.demo = demo
        self.jpeg = None
        self.updated = None
        self.previous = None
        self.sequence = 0
        self.people = []
        self.events = deque(maxlen=100)
        self.counts = Counter()
        self.processing_ms = 0.0
        self.fps = 0.0
        self.dropped = 0
        self.metrics = metrics or ObservabilityMetrics()
        self.health = health or HealthStatus()
        self.camera_id = "default"
        self.event_sequence = 0

    def set_status(self, status, error=None):
        with self.lock:
            self.status, self.error = status, error
        self.health.set_ready(source_connected=status == "running")
        if status == "error":
            self.metrics.increment("vision_core_errors_total")

    def event(self, event):
        with self.lock:
            self.events.appendleft(self._event_serializer(event))
            self.counts[event.event] += 1
        self.event_sequence += 1
        event_id = f"{self.camera_id}-{self.event_sequence}"
        logger.info(
            "Vision event emitted",
            extra={
                "camera_id": self.camera_id,
                "event_id": event_id,
                "person_id": event.person_id,
                "error_code": None,
            },
        )
        self.metrics.increment("vision_core_events_emitted_total")
        self.metrics.increment(f"vision_core_event_{event.event.lower()}_total")

    def person_label(self, person_id):
        with self.lock:
            number = self._person_numbers.setdefault(person_id, len(self._person_numbers) + 1)
            return f"Persona {number}"

    def publish(self, jpeg, people, processing_ms, dropped=0):
        now = time.monotonic()
        with self.lock:
            if self.previous is not None:
                current = 1 / max(now - self.previous, 0.000001)
                self.fps = current if not self.fps else 0.8 * self.fps + 0.2 * current
            self.previous = now
            self.updated = time.time()
            self.sequence += 1
            self.jpeg = jpeg
            self.people = people
            self.processing_ms = processing_ms
            self.dropped = dropped
            self.status = "running"
            self.changed.notify_all()
        self.health.set_ready(source_connected=True, model_loaded=True)
        self.metrics.increment("vision_core_frames_processed_total")
        self.metrics.increment("vision_core_frames_discarded_total", dropped)
        self.metrics.set_gauge("vision_core_fps", self.fps)
        self.metrics.set_gauge("vision_core_active_people", len(people))
        self.metrics.set_gauge("vision_core_queue_size", 0)
        self.metrics.observe("vision_core_frame_processing_duration_ms", processing_ms)

    def next_frame(self, after):
        with self.changed:
            self.changed.wait_for(lambda: self.sequence > after, timeout=1)
            if self.sequence <= after or self.jpeg is None:
                return None, self.sequence
            return self.jpeg, self.sequence

    def current_frame(self):
        with self.lock:
            return self.jpeg, self.sequence

    def snapshot(self):
        with self.lock:
            age = time.time() - self.updated if self.updated is not None else None
            status = "stale" if self.status == "running" and age > 5 else self.status
            return {
                "status": status,
                "error": self.error,
                "demo_zones": self.demo,
                "frame": self.sequence,
                "updated_at": self.updated,
                "age_seconds": age,
                "people": self.people if status == "running" else [],
                "events": list(self.events),
                "counts": dict(self.counts),
                "processing_ms": self.processing_ms,
                "fps": self.fps,
                "dropped_frames": self.dropped,
            }
