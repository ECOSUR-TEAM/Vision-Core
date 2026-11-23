import hashlib
import platform
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    if not 0 <= quantile <= 1:
        raise ValueError("quantile debe estar entre 0 y 1")
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 4)
    rank = (len(ordered) - 1) * quantile
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    result = ordered[lower] * (1 - weight) + ordered[upper] * weight
    return round(result, 4)


def summarize_latencies(samples_ms: list[float]) -> dict[str, float | None | int]:
    return {
        "samples": len(samples_ms),
        "p50_ms": percentile(samples_ms, 0.5),
        "p95_ms": percentile(samples_ms, 0.95),
        "mean_ms": _mean(samples_ms),
    }


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def sha256_file(path: str | Path) -> str:
    source = Path(path)
    digest = hashlib.sha256()
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_energy_uj() -> float | None:
    roots = [path for path in Path("/sys/class/powercap").glob("intel-rapl:[0-9]*") if path.is_dir()]
    total = 0.0
    for root in roots:
        sensor = root / "energy_uj"
        if not sensor.is_file():
            continue
        try:
            total += float(sensor.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            continue
    return total if roots else None


def environment_metadata(device: str, config_sha256: str) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "processor": platform.processor() or "unknown",
        "device_declared": device,
        "config_sha256": config_sha256,
        "cuda_available": False,
    }
    for package in ("torch", "torchvision", "ultralytics", "numpy"):
        try:
            metadata[package] = version(package)
        except PackageNotFoundError:
            metadata[package] = None
    try:
        import torch

        metadata["cuda_available"] = torch.cuda.is_available()
    except ImportError:
        pass
    return metadata
