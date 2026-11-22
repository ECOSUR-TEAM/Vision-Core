import threading
import time

from vision_core.core.config.persistence import PersistenceSettings
from vision_core.core.domain.event import Event
from vision_core.core.infrastructure.persistence.persistence_service import PersistenceService
from vision_core.core.infrastructure.persistence.retention_job import RetentionJob
from vision_core.core.infrastructure.persistence.retention_worker import RetentionWorker


def _settings(tmp_path, **overrides):
    values = {
        "VISION_CORE_DB_PATH": str(tmp_path / "retention.sqlite3"),
        "VISION_CORE_EVENT_TTL_SECONDS": "10",
        "VISION_CORE_HISTORY_TTL_SECONDS": "10",
        "VISION_CORE_IDENTITY_TTL_SECONDS": "10",
        "VISION_CORE_TRACK_TTL_SECONDS": "10",
        "VISION_CORE_SESSION_TTL_SECONDS": "10",
        "VISION_CORE_METRICS_TTL_SECONDS": "10",
    }
    values.update(overrides)
    return PersistenceSettings.from_env(values)


def test_retention_deletes_each_data_type_according_to_its_ttl(tmp_path):
    service = PersistenceService(_settings(tmp_path))
    service.start_session("old-session", 900.0)
    service.start_session("new-session", 1000.0)
    service.append_event(Event("PERSON_ENTERED", "old", 900.0, event_id="old"), "old-session")
    service.append_event(Event("PERSON_ENTERED", "new", 1000.0, event_id="new"), "new-session")
    service.zone_observations.append("old", "z", (0.0, 0.0), 900.0, "old")
    service.zone_observations.append("new", "z", (0.0, 0.0), 1000.0, "new")
    service.identities.save("old", [1.0], 900.0)
    service.identities.save("new", [1.0], 1000.0)
    service.tracks.append("old-session", 1, "old", (0, 0, 1, 1), 900.0)
    service.tracks.append("new-session", 1, "new", (0, 0, 1, 1), 1000.0)
    service.metrics.record("old-session", "events", 1.0, 900.0)
    service.metrics.record("new-session", "events", 1.0, 1000.0)

    result = RetentionJob(service).run_once(now=1000.0)

    assert result.events == 1
    assert result.zone_observations == 1
    assert result.tracks == 1
    assert result.identities == 1
    assert result.persons == 1
    assert result.sessions == 1
    assert result.metrics == 1
    assert [event.event_id for event in service.events.list()] == ["new"]
    assert [row[0] for row in service.sessions.list()] == ["new-session"]
    service.close()


def test_zero_ttl_disables_deletion_for_that_type(tmp_path):
    service = PersistenceService(_settings(tmp_path, VISION_CORE_EVENT_TTL_SECONDS="0"))
    service.append_event(Event("PERSON_ENTERED", "old", 1.0, event_id="old"))

    result = RetentionJob(service).run_once(now=10_000.0)

    assert result.events == 0
    assert len(service.events.list()) == 1
    service.close()


def test_retention_worker_runs_job_in_background(tmp_path):
    service = PersistenceService(_settings(tmp_path))
    job = RetentionJob(service)
    gate = threading.Event()

    def fake_sleep(_interval):
        gate.wait(timeout=1)

    worker = RetentionWorker(job, interval_seconds=1, sleep=fake_sleep, clock=lambda: 5000.0)
    worker.start()
    gate.set()
    deadline = time.time() + 2
    while job.last_result is None and time.time() < deadline:
        time.sleep(0.01)
    worker.stop(timeout=1)

    assert job.last_result is not None
    assert not worker.running
    service.close()
