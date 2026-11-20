import sqlite3
import time

from vision_core.domain.model.event import Event
from vision_core.infrastructure.persistence.event_identity import event_id_for
from vision_core.infrastructure.persistence.persistence_service import PersistenceService
from vision_core.settings.persistence import PersistenceSettings


def _service(tmp_path):
    settings = PersistenceSettings.from_env({"VISION_CORE_DB_PATH": str(tmp_path / "events.sqlite3")})
    return PersistenceService(settings)


def test_append_event_is_idempotent_by_explicit_id(tmp_path):
    service = _service(tmp_path)
    event = Event("PERSON_ENTERED", "person-1", 100.0, {"to_zone": "z", "position": [1, 2]}, event_id="evt-1")

    assert service.append_event(event) is True
    assert service.append_event(event) is False
    assert len(service.events.list()) == 1
    assert service.zone_observations.list() == (("person-1", "z", (1.0, 2.0), 100.0),)
    service.close()


def test_event_and_zone_observation_are_atomic(monkeypatch, tmp_path):
    service = _service(tmp_path)
    event = Event("PERSON_ENTERED", "person-1", 100.0, {"to_zone": "z", "position": [1, 2]}, event_id="atomic")
    original = service.zone_observations.append_with
    state = {"fail": True}

    def append_with(*args, **kwargs):
        if state["fail"]:
            raise sqlite3.OperationalError("boom")
        return original(*args, **kwargs)

    monkeypatch.setattr(service.zone_observations, "append_with", append_with)
    assert service.append_event(event) is False
    assert service.events.list() == ()
    assert service.health()["failures"] == 1

    state["fail"] = False
    assert service.append_event(event) is True
    assert service.zone_observations.list() == (("person-1", "z", (1.0, 2.0), 100.0),)
    service.close()


def test_duplicate_event_retry_restores_zone_observation(tmp_path):
    service = _service(tmp_path)
    event = Event("PERSON_ENTERED", "person-1", 100.0, {"to_zone": "z", "position": [1, 2]}, event_id="retry")

    assert service.events.append(event) is True
    assert service.zone_observations.list() == ()
    assert service.append_event(event) is False
    assert service.zone_observations.list() == (("person-1", "z", (1.0, 2.0), 100.0),)
    service.close()


def test_event_does_not_generate_a_random_identifier():
    assert Event("PERSON_ENTERED", "person-1").event_id == ""


def test_append_event_derives_stable_id_when_missing(tmp_path):
    service = _service(tmp_path)
    first = Event("PERSON_EXITED", "person-2", 101.0, event_id="")
    second = Event("PERSON_EXITED", "person-2", 101.0, event_id="")
    assert event_id_for(first) == event_id_for(second)

    assert service.append_event(first, "session-1") is True
    assert service.append_event(second, "session-1") is False
    assert [row.event_id for row in service.events.list()] == [event_id_for(first)]
    service.close()


def test_events_can_be_queried_and_survive_restart(tmp_path):
    service = _service(tmp_path)
    service.start_session("session-1", time.time())
    service.append_event(Event("PERSON_ENTERED", "p1", 10.0, event_id="a"), "session-1")
    service.append_event(Event("PERSON_EXITED", "p1", 20.0, event_id="b"), "session-1")
    service.append_event(Event("PERSON_ENTERED", "p2", 30.0, event_id="c"), "session-2")
    service.close()

    reopened = _service(tmp_path)
    assert len(reopened.events.list(person_id="p1")) == 2
    assert len(reopened.events.list(session_id="session-1")) == 2
    assert len(reopened.events.list(since=25.0)) == 1
    assert [event.event_id for event in reopened.events.list(limit=1)] == ["a"]
    assert reopened.append_event(Event("PERSON_ENTERED", "p1", 10.0, event_id="a")) is False
    reopened.close()
