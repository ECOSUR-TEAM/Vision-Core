"""Contadores de peticiones rechazadas por los límites del monitor."""

import logging
import threading

_LOGGER = logging.getLogger(__name__)
_LOG_SAMPLE_EVERY = 50


class MonitorLimitsMetrics:
    """Cuenta rechazos sin registrar URLs, payloads ni direcciones."""

    _REASONS = ("concurrency", "long_poll_concurrency", "timeout", "oversized")

    def __init__(self):
        self._lock = threading.Lock()
        self._counts = {reason: 0 for reason in self._REASONS}

    def record(self, reason):
        with self._lock:
            self._counts[reason] = self._counts.get(reason, 0) + 1
            count = self._counts[reason]
        if count == 1 or count % _LOG_SAMPLE_EVERY == 0:
            _LOGGER.debug("monitor_request_rejected reason=%s count=%s", reason, count)

    def snapshot(self):
        with self._lock:
            return dict(self._counts)
