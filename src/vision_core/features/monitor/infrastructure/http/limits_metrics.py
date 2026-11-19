"""Thread-safe counters for rejected monitor requests."""

import logging
import threading

_LOGGER = logging.getLogger(__name__)
_LOG_SAMPLE_EVERY = 50


class MonitorLimitsMetrics:
    """Count rejected requests without logging URLs, payloads or addresses."""

    _REASONS = ("concurrency", "long_poll_concurrency", "timeout", "oversized")

    def __init__(self):
        self._lock = threading.Lock()
        self._counts = {reason: 0 for reason in self._REASONS}

    def record(self, reason):
        with self._lock:
            self._counts[reason] = self._counts.get(reason, 0) + 1
            count = self._counts[reason]
        # Debug-level and sampled so a client cannot fill the logs by
        # repeatedly tripping a limit.
        if count == 1 or count % _LOG_SAMPLE_EVERY == 0:
            _LOGGER.debug("monitor_request_rejected reason=%s count=%s", reason, count)

    def snapshot(self):
        with self._lock:
            return dict(self._counts)
