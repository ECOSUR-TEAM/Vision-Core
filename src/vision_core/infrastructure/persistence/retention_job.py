import time

from vision_core.infrastructure.persistence.persistence_service import PersistenceService
from vision_core.infrastructure.persistence.retention_result import RetentionResult


class RetentionJob:
    def __init__(self, service: PersistenceService, *, clock=time.time):
        self._service = service
        self._clock = clock
        self.last_result: RetentionResult | None = None

    def run_once(self, now: float | None = None) -> RetentionResult:
        instant = self._clock() if now is None else now
        settings = self._service.settings
        result = RetentionResult(
            events=self._delete(settings.event_ttl_seconds, instant, self._service.events.delete_older_than),
            zone_observations=self._delete(
                settings.history_ttl_seconds,
                instant,
                self._service.zone_observations.delete_older_than,
            ),
            tracks=self._delete(settings.track_ttl_seconds, instant, self._service.tracks.delete_older_than),
            identities=self._delete(
                settings.identity_ttl_seconds,
                instant,
                self._service.identities.delete_older_than,
            ),
            persons=self._delete(
                settings.identity_ttl_seconds,
                instant,
                self._service.identities.delete_persons_older_than,
            ),
            metrics=self._delete(
                settings.metrics_ttl_seconds,
                instant,
                self._service.metrics.delete_older_than,
            ),
            sessions=self._delete(
                settings.session_ttl_seconds,
                instant,
                self._service.sessions.delete_older_than,
            ),
        )
        self.last_result = result
        return result

    def _delete(self, ttl: float, now: float, operation) -> int:
        if not self._service.settings.enabled or ttl <= 0:
            return 0
        cutoff = now - ttl
        return int(self._service._guard(lambda: operation(cutoff), 0) or 0)
