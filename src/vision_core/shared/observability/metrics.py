import threading
import time


class ObservabilityMetrics:
    """Thread-safe in-process counters, gauges and histograms."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}
        self.started_at = time.time()

    def increment(self, name: str, value: float = 1.0) -> None:
        with self._lock:
            self._counters[name] = self._counters.get(name, 0.0) + value

    def set_gauge(self, name: str, value: float) -> None:
        with self._lock:
            self._gauges[name] = value

    def observe(self, name: str, value: float) -> None:
        with self._lock:
            values = self._histograms.setdefault(name, [])
            values.append(value)
            if len(values) > 1000:
                del values[:500]

    def snapshot(self) -> dict:
        with self._lock:
            counters = dict(self._counters)
            gauges = dict(self._gauges)
            histograms = {}
            for name, values in self._histograms.items():
                if values:
                    histograms[name] = {
                        "count": len(values),
                        "sum": sum(values),
                        "min": min(values),
                        "max": max(values),
                        "avg": sum(values) / len(values),
                    }
                else:
                    histograms[name] = {"count": 0, "sum": 0, "min": 0, "max": 0, "avg": 0}
            return {
                "counters": counters,
                "gauges": gauges,
                "histograms": histograms,
                "uptime_seconds": time.time() - self.started_at,
            }


_DEFAULT_METRICS = ObservabilityMetrics()


def get_observability_metrics() -> ObservabilityMetrics:
    return _DEFAULT_METRICS
