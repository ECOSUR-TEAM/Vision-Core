"""Helpers compartidos por los tests del slice de eventos."""

import time

from vision_core.core.dto.event_envelope import EventEnvelope
from vision_core.core.serialization import EVENT_SCHEMA_VERSION


def make_envelope(event_id: str = "evt-1", event: str = "PERSON_ENTERED") -> EventEnvelope:
    return EventEnvelope(
        event_id=event_id,
        payload={
            "event": event,
            "person_id": "person-1",
            "timestamp": 10.0,
            "metadata": {},
            "schema_version": EVENT_SCHEMA_VERSION,
        },
    )


def wait_until(predicate, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError("la condición no se cumplió antes del timeout")
        time.sleep(0.005)
