"""High-resolution timing for the sequential inference stages."""

import json
import math
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from time import perf_counter

STAGES = ("decode", "detection", "embedding", "reid_tracking", "analytics", "frame_total")


def _percentile(samples: list[float], quantile: float) -> float:
    """Nearest-rank percentile; returns 0.0 for an empty sample list."""
    if not samples:
        return 0.0
    ordered = sorted(samples)
    index = min(len(ordered) - 1, max(0, math.ceil(quantile * len(ordered)) - 1))
    return ordered[index] * 1000.0


class FrameProfiler:
    """Acumula duraciones ``perf_counter`` y guarda p50/p95/FPS al finalizar."""

    def __init__(self, enabled: bool = True, camera_id: str = "default") -> None:
        self._enabled = bool(enabled)
        self._camera_id = camera_id or "default"
        self._samples: dict[str, list[float]] = {stage: [] for stage in STAGES}
        self._frames = 0
        self._started = perf_counter()

    @property
    def enabled(self) -> bool:
        return self._enabled

    def reset(self) -> None:
        self._samples = {stage: [] for stage in STAGES}
        self._frames = 0
        self._started = perf_counter()

    def record_frame(self) -> None:
        self._frames += 1

    def record(self, stage: str, seconds: float) -> None:
        if not self._enabled:
            return
        self._samples.setdefault(stage, []).append(float(seconds))

    @contextmanager
    def measure(self, stage: str) -> Iterator[None]:
        if not self._enabled:
            yield
            return
        started = perf_counter()
        try:
            yield
        finally:
            self.record(stage, perf_counter() - started)

    def summary(self) -> dict:
        elapsed = max(perf_counter() - self._started, 0.0)
        stages = {}
        for stage, samples in self._samples.items():
            stages[stage] = {
                "samples": len(samples),
                "p50_ms": round(_percentile(samples, 0.50), 4),
                "p95_ms": round(_percentile(samples, 0.95), 4),
                "mean_ms": round((sum(samples) / len(samples)) * 1000, 4) if samples else 0.0,
                "max_ms": round(max(samples, default=0.0) * 1000, 4),
            }
        return {
            "camera_id": self._camera_id,
            "frames": self._frames,
            "elapsed_seconds": round(elapsed, 6),
            "fps": round(self._frames / elapsed, 2) if elapsed > 0 else 0.0,
            "stages": stages,
        }

    def save(self, path: str | Path) -> Path:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(self.summary(), indent=2, allow_nan=False) + "\n", encoding="utf-8")
        return output
