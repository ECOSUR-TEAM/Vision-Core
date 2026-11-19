import logging
import sqlite3
import time

from vision_core.domain.model.event import Event
from vision_core.domain.types import Embedding
from vision_core.infrastructure.persistence.connection import Database
from vision_core.infrastructure.persistence.event_identity import event_id_for
from vision_core.infrastructure.persistence.migration_runner import MigrationRunner
from vision_core.infrastructure.persistence.sqlite_event_repository import SqliteEventRepository
from vision_core.infrastructure.persistence.sqlite_identity_repository import SqliteIdentityRepository
from vision_core.infrastructure.persistence.sqlite_metrics_repository import SqliteMetricsRepository
from vision_core.infrastructure.persistence.sqlite_session_repository import SqliteSessionRepository
from vision_core.infrastructure.persistence.sqlite_track_repository import SqliteTrackRepository
from vision_core.infrastructure.persistence.sqlite_zone_observation_repository import (
    SqliteZoneObservationRepository,
)
from vision_core.infrastructure.persistence.sqlite_zone_repository import SqliteZoneRepository
from vision_core.settings.persistence import PersistenceSettings

logger = logging.getLogger(__name__)


class PersistenceService:
    def __init__(self, settings: PersistenceSettings):
        self.settings = settings
        self._database = Database(settings.db_path, busy_timeout_seconds=settings.busy_timeout_seconds, migrate=False)
        self.events = SqliteEventRepository(self._database)
        self.zone_observations = SqliteZoneObservationRepository(self._database)
        self.identities = SqliteIdentityRepository(self._database)
        self.tracks = SqliteTrackRepository(self._database)
        self.sessions = SqliteSessionRepository(self._database)
        self.metrics = SqliteMetricsRepository(self._database)
        self.zones = SqliteZoneRepository(self._database)
        self._migrations: tuple[str, ...] = ()
        self._failures = 0
        self._last_error: str | None = None
        if settings.enabled:
            self._run_migrations()

    def _run_migrations(self) -> None:
        try:
            self._migrations = MigrationRunner(self._database.connection()).migrate()
        except (sqlite3.Error, OSError) as error:
            self._record_failure(error)
            if not self.settings.fail_open:
                raise

    def _record_failure(self, error: Exception) -> None:
        self._failures += 1
        self._last_error = str(error)
        if self._failures == 1 or self._failures % 100 == 0:
            logger.warning("persistence operation failed (%s): %s", self._failures, error)

    def _guard(self, operation, fallback=None):
        if not self.settings.enabled:
            return fallback
        try:
            return operation()
        except (sqlite3.Error, OSError) as error:
            self._record_failure(error)
            if not self.settings.fail_open:
                raise
            return fallback

    def append_event(self, event: Event, session_id: str | None = None) -> bool:
        def operation() -> bool:
            metadata = event.metadata or {}
            zone = metadata.get("to_zone")
            position = metadata.get("position")
            connection = self._database.connection()
            with self._database.lock, connection:
                inserted = self.events.append_with(connection, event, session_id)
                if inserted and zone is not None and position is not None and len(position) == 2:
                    self.zone_observations.append_with(
                        connection,
                        event.person_id,
                        str(zone),
                        (float(position[0]), float(position[1])),
                        event.timestamp,
                        event_id_for(event),
                    )
                return inserted

        return bool(self._guard(operation, False))

    def list_events(self, **filters) -> tuple[Event, ...]:
        return tuple(self._guard(lambda: self.events.list(**filters), ()) or ())

    def append_track(
        self,
        session_id: str,
        track_id: int,
        person_id: str,
        bbox: tuple[float, float, float, float],
        timestamp: float,
    ) -> bool:
        return bool(self._guard(lambda: self.tracks.append(session_id, track_id, person_id, bbox, timestamp), False))

    def save_identity(self, person_id: str, embedding: Embedding, last_seen_at: float) -> bool:
        return bool(self._guard(lambda: self.identities.save(person_id, embedding, last_seen_at), False))

    def list_identities(self, *, since: float) -> tuple[tuple[str, tuple[float, ...], float], ...]:
        return tuple(self._guard(lambda: self.identities.list_active(since=since), ()) or ())

    def start_session(self, session_id: str, started_at: float, camera_id: str | None = None) -> bool:
        return bool(self._guard(lambda: self.sessions.start(session_id, started_at, camera_id), False))

    def finish_session(self, session_id: str, finished_at: float) -> bool:
        return bool(self._guard(lambda: self.sessions.finish(session_id, finished_at), False))

    def record_metric(self, session_id: str, name: str, value: float, timestamp: float) -> bool:
        return bool(self._guard(lambda: self.metrics.record(session_id, name, value, timestamp), False))

    def save_zones(self, definitions) -> bool:
        def operation() -> bool:
            timestamp = time.time()
            for definition in definitions:
                name = getattr(definition, "name", None)
                points = getattr(definition, "points", None)
                if name is not None and points is not None:
                    self.zones.save(str(name), tuple((float(x), float(y)) for x, y in points), timestamp)
            return True

        return bool(self._guard(operation, False))

    def health(self) -> dict[str, object]:
        return {
            "enabled": self.settings.enabled,
            "path": str(self.settings.db_path),
            "migrations": list(self._migrations),
            "failures": self._failures,
            "last_error": self._last_error,
        }

    def close(self) -> None:
        if self.settings.enabled:
            self._database.close()
