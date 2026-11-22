import re
import threading
import time


class ObservabilityMetrics:
    """Thread-safe in-process counters, gauges and histograms."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}
        self._histogram_totals: dict[str, tuple[int, float]] = {}
        self.started_at = time.monotonic()

    @staticmethod
    def _keys(name: str, camera_id: str | None) -> tuple[str, ...]:
        if not camera_id or camera_id == "default":
            return (name,)
        safe_id = re.sub(r"[^A-Za-z0-9_.:-]+", "_", camera_id)
        return (name, f"{name}{{camera_id={safe_id}}}")

    def increment(self, name: str, value: float = 1.0, *, camera_id: str | None = None) -> None:
        with self._lock:
            for key in self._keys(name, camera_id):
                self._counters[key] = self._counters.get(key, 0.0) + value

    def set_gauge(self, name: str, value: float, *, camera_id: str | None = None) -> None:
        with self._lock:
            for key in self._keys(name, camera_id):
                self._gauges[key] = value

    def observe(self, name: str, value: float, *, camera_id: str | None = None) -> None:
        with self._lock:
            for key in self._keys(name, camera_id):
                values = self._histograms.setdefault(key, [])
                values.append(value)
                if len(values) > 1000:
                    del values[:500]
                total_count, total_sum = self._histogram_totals.get(key, (0, 0.0))
                self._histogram_totals[key] = (total_count + 1, total_sum + value)

    def snapshot(self) -> dict:
        with self._lock:
            counters = dict(self._counters)
            gauges = dict(self._gauges)
            histograms = {}
            for name, values in self._histograms.items():
                total_count, total_sum = self._histogram_totals.get(name, (0, 0.0))
                if values:
                    histograms[name] = {
                        "count": total_count,
                        "sum": total_sum,
                        "min": min(values),
                        "max": max(values),
                        "avg": total_sum / total_count if total_count else 0,
                    }
                else:
                    histograms[name] = {"count": 0, "sum": 0, "min": 0, "max": 0, "avg": 0}
            return {
                "counters": counters,
                "gauges": gauges,
                "histograms": histograms,
                "uptime_seconds": time.monotonic() - self.started_at,
            }


_DEFAULT_METRICS = ObservabilityMetrics()


def get_observability_metrics() -> ObservabilityMetrics:
    return _DEFAULT_METRICS
