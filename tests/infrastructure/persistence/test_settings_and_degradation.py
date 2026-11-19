import pytest

from vision_core.domain.model.event import Event
from vision_core.infrastructure.persistence.persistence_service import PersistenceService
from vision_core.settings.persistence import PersistenceSettings


def test_persistence_is_disabled_without_db_path():
    settings = PersistenceSettings.from_env({})
    service = PersistenceService(settings)

    assert settings.enabled is False
    assert service.append_event(Event("PERSON_ENTERED", "p1", event_id="e1")) is False
    assert service.health()["enabled"] is False
    assert service.list_events() == ()
    service.close()


def test_settings_are_read_from_environment(tmp_path):
    settings = PersistenceSettings.from_env(
        {
            "VISION_CORE_DB_PATH": str(tmp_path / "db.sqlite3"),
            "VISION_CORE_DB_ENABLED": "0",
            "VISION_CORE_DB_FAIL_OPEN": "false",
            "VISION_CORE_EVENT_TTL_SECONDS": "60",
            "VISION_CORE_DB_PRUNE_INTERVAL_SECONDS": "30",
        }
    )

    assert settings.db_path == tmp_path / "db.sqlite3"
    assert settings.enabled is False
    assert settings.fail_open is False
    assert settings.event_ttl_seconds == 60
    assert settings.prune_interval_seconds == 30


def test_invalid_numeric_setting_is_rejected():
    with pytest.raises(ValueError, match="numérico"):
        PersistenceSettings.from_env({"VISION_CORE_EVENT_TTL_SECONDS": "not-a-number"})


def test_database_failure_degrades_without_raising(tmp_path):
    blocked_path = tmp_path / "not-a-file"
    blocked_path.mkdir()
    settings = PersistenceSettings.from_env({"VISION_CORE_DB_PATH": str(blocked_path)})
    service = PersistenceService(settings)

    assert service.append_event(Event("PERSON_ENTERED", "p1", event_id="e1")) is False
    health = service.health()
    assert health["enabled"] is True
    assert health["failures"] >= 2
    assert health["last_error"]
    service.close()
