"""Clave de idempotencia estable y payload intacto del ticket 31."""

from vision_core.core.domain.event import Event
from vision_core.core.serialization import EVENT_SCHEMA_VERSION
from vision_core.features.events.domain.event_envelope_factory import envelope_for


def test_explicit_event_id_is_preserved_as_idempotency_key():
    event = Event("PERSON_ENTERED", "p1", 10.0, event_id="evt-explicit")
    envelope = envelope_for(event)
    assert envelope.event_id == "evt-explicit"
    assert envelope.payload["event"] == "PERSON_ENTERED"
    assert envelope.payload["schema_version"] == EVENT_SCHEMA_VERSION


def test_missing_event_id_uses_stable_hash_between_restarts():
    first = envelope_for(Event("PERSON_EXITED", "p2", 20.0))
    second = envelope_for(Event("PERSON_EXITED", "p2", 20.0))
    assert first.event_id == second.event_id
    assert len(first.event_id) == 64
