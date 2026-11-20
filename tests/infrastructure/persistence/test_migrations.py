import sqlite3

import pytest

from vision_core.infrastructure.persistence.connection import Database
from vision_core.infrastructure.persistence.migration_runner import MigrationRunner


def test_migrations_create_schema_from_scratch(tmp_path):
    database = Database(tmp_path / "core.sqlite3", migrate=False)
    runner = MigrationRunner(database.connection())

    applied = runner.migrate()

    assert applied == ("001_initial", "002_metrics")
    connection = database.connection()
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {
        "schema_migrations",
        "sessions",
        "persons",
        "zones",
        "events",
        "zone_observations",
        "tracks",
        "identity_gallery",
        "metrics",
    } <= tables
    database.close()


def test_migrations_upgrade_preserves_existing_data(tmp_path):
    database = Database(tmp_path / "core.sqlite3", migrate=False)
    runner = MigrationRunner(database.connection())
    runner.migrate(target="001_initial")

    connection = database.connection()
    connection.execute(
        "INSERT INTO events(event_id, event_type, person_id, timestamp_utc, metadata_json, created_at_utc) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("evt-1", "PERSON_ENTERED", "person-1", 10.0, "{}", "2026-11-19T00:00:00.000Z"),
    )
    connection.commit()

    assert runner.migrate() == ("002_metrics",)
    rows = connection.execute("SELECT event_id FROM events").fetchall()
    assert [row[0] for row in rows] == ["evt-1"]
    assert [row[0] for row in connection.execute("SELECT version FROM schema_migrations ORDER BY version")] == [
        "001_initial",
        "002_metrics",
    ]
    database.close()


def test_migrations_reject_unknown_target(tmp_path):
    database = Database(tmp_path / "core.sqlite3", migrate=False)
    try:
        MigrationRunner(database.connection()).migrate(target="999_missing")
    except ValueError as error:
        assert "999_missing" in str(error)
    else:
        raise AssertionError("Se esperaba ValueError")
    finally:
        database.close()


def test_event_id_is_unique_in_schema(tmp_path):
    database = Database(tmp_path / "core.sqlite3", migrate=False)
    MigrationRunner(database.connection()).migrate()
    connection = database.connection()
    values = ("evt-1", "PERSON_ENTERED", "person-1", 10.0, "{}", "2026-11-19T00:00:00.000Z")
    connection.execute(
        "INSERT INTO events(event_id, event_type, person_id, timestamp_utc, metadata_json, created_at_utc) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        values,
    )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO events(event_id, event_type, person_id, timestamp_utc, metadata_json, created_at_utc) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            values,
        )
    database.close()
