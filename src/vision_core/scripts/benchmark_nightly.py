"""Benchmark reproducible del pipeline real con video sintético y presupuestos."""

import argparse
import csv
import json
import time
import tracemalloc
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from vision_core.application.pipeline_config import PipelineConfig
from vision_core.core.telemetry.metrics import ObservabilityMetrics
from vision_core.features.detection.domain.ports.detector_manager import DetectorManager
from vision_core.features.door.infrastructure.adapters.polygon_door_analytics import PolygonDoorAnalytics
from vision_core.features.door.infrastructure.config.zone_config import ZoneConfig
from vision_core.features.door.infrastructure.config.zone_loader import load_zones
from vision_core.features.pipeline.application.mappers.pipeline_mapper import event_to_json
from vision_core.features.pipeline.application.use_cases.run_pipeline import RunPipeline
from vision_core.features.reid.infrastructure.adapters.memory_reid import InMemoryReID
from vision_core.features.video.domain.ports.video_source import VideoSource
from vision_core.features.video.infrastructure.adapters import rtsp_video_source as rtsp_module
from vision_core.features.video.infrastructure.adapters.file_video_source import FileVideoSource
from vision_core.features.video.infrastructure.adapters.rtsp_video_source import RtspVideoSource
from vision_core.scripts.benchmark_metadata import environment_metadata
from vision_core.scripts.fake_reconnect_capture import FakeReconnectCapture
from vision_core.scripts.synthetic_detector import SyntheticDetector

BUDGET_RULES = {
    "fps": ("fps_min", "min"),
    "frame_p50_ms": ("frame_p50_max_ms", "max"),
    "frame_p95_ms": ("frame_p95_max_ms", "max"),
    "inference_p50_ms": ("inference_p50_max_ms", "max"),
    "inference_p95_ms": ("inference_p95_max_ms", "max"),
    "memory_peak_mb": ("memory_peak_max_mb", "max"),
    "memory_growth_mb_per_hour": ("memory_growth_per_hour_max_mb", "max"),
    "startup_ms": ("startup_max_ms", "max"),
    "reconnect_ms": ("reconnect_max_ms", "max"),
}
MIN_GROWTH_SAMPLE_SECONDS = 30.0
REGRESSION_RULES = {
    "fps": "min",
    "frame_p50_ms": "max",
    "frame_p95_ms": "max",
    "inference_p95_ms": "max",
    "memory_peak_tracemalloc_mb": "max",
    "memory_growth_mb_per_hour": "max",
}
HOTSPOT_LABELS = {
    "decode": "captura/decode",
    "detection": "detección",
    "embedding": "embedding ReID",
    "reid_tracking": "tracking/ReID",
    "analytics": "puerta/zonas",
    "serialization": "serialización",
}
METRIC_LABELS = {
    "fps": "FPS",
    "frame_p50_ms": "Frame p50 (ms)",
    "frame_p95_ms": "Frame p95 (ms)",
    "inference_p50_ms": "Inferencia p50 (ms)",
    "inference_p95_ms": "Inferencia p95 (ms)",
    "memory_peak_mb": "Memoria pico (MB)",
    "memory_peak_tracemalloc_mb": "Memoria pico comparable (MB)",
    "memory_growth_mb_per_hour": "Crecimiento memoria (MB/h)",
    "startup_ms": "Arranque a primer frame (ms)",
    "reconnect_ms": "Reconexión (ms)",
}


def load_budgets(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("scenarios"), dict):
        raise ValueError("El archivo de presupuestos debe tener schema_version=1 y scenarios")
    return data


def memory_growth_mb_per_hour(
    initial: dict[str, Any],
    final: dict[str, Any],
    elapsed_seconds: float,
) -> float:
    initial_mb = float(initial["tracemalloc_current_mb"])
    final_mb = float(final["tracemalloc_current_mb"])
    window = max(float(elapsed_seconds), MIN_GROWTH_SAMPLE_SECONDS)
    return round(max(0.0, (final_mb - initial_mb) / window * 3600), 3)


def _memory_usage() -> dict[str, Any]:
    current, peak = tracemalloc.get_traced_memory()
    result: dict[str, Any] = {
        "tracemalloc_current_mb": round(current / 1048576, 3),
        "tracemalloc_peak_mb": round(peak / 1048576, 3),
        "rss_current_mb": None,
        "rss_peak_mb": None,
        "source": "tracemalloc",
    }
    status = Path("/proc/self/status")
    if status.is_file():
        values: dict[str, float] = {}
        for line in status.read_text(encoding="utf-8").splitlines():
            if line.startswith(("VmRSS:", "VmHWM:")):
                key, raw = line.split(":", 1)
                values[key] = float(raw.split()[0]) / 1024
        result["rss_current_mb"] = round(values["VmRSS"], 3) if "VmRSS" in values else None
        result["rss_peak_mb"] = round(values["VmHWM"], 3) if "VmHWM" in values else None
        if "VmHWM" in values:
            result["source"] = "proc-status"
    return result


def measure_reconnection_ms() -> float:
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    captures = [
        FakeReconnectCapture([(True, frame), (False, None)]),
        FakeReconnectCapture([(True, frame)]),
    ]
    original = rtsp_module.cv2.VideoCapture

    def next_capture(*args: Any, **kwargs: Any) -> FakeReconnectCapture:
        return captures.pop(0)

    source = RtspVideoSource(
        "rtsp://127.0.0.1:8554/benchmark",
        reconnect_attempts=1,
        reconnect_delay_seconds=0.0,
    )
    try:
        setattr(rtsp_module.cv2, "VideoCapture", next_capture)
        started = time.perf_counter()
        source.open()
        initial = source.read_frame()
        recovered = source.read_frame()
        elapsed = (time.perf_counter() - started) * 1000
    finally:
        setattr(rtsp_module.cv2, "VideoCapture", original)
        source.close()
    if initial is None or recovered is None or source.reconnections != 1:
        raise RuntimeError("La medición de reconexión no logró recuperar el stream simulado")
    return round(elapsed, 4)


def run_benchmark(
    *,
    source: VideoSource,
    zones: ZoneConfig,
    detector: DetectorManager,
    video_path: str | Path,
    output_dir: str | Path,
    scenario: str,
    device: str,
    confirmation_frames: int = 2,
    context: str = "",
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    reconnect_ms = measure_reconnection_ms()
    build_started = time.perf_counter()
    outside_tracing = not tracemalloc.is_tracing()
    if outside_tracing:
        tracemalloc.start()
    else:
        tracemalloc.reset_peak()
    initial_memory = _memory_usage()
    observability = ObservabilityMetrics()
    event_counts: Counter[str] = Counter()
    first_frame: dict[str, float] = {}
    pipeline_holder: dict[str, Any] = {}

    analytics = PolygonDoorAnalytics(
        zones.exterior,
        zones.interior,
        zones.door,
        confirmation_frames=confirmation_frames,
    )

    def on_event(event: Any) -> None:
        event_counts[event.event] += 1
        started = time.perf_counter()
        event_to_json(event)
        if "pipeline" in pipeline_holder:
            pipeline_holder["pipeline"].profiler.record("serialization", time.perf_counter() - started)

    def on_frame(frame: Any, tracks: Any, processing_ms: float) -> None:
        first_frame.setdefault("at", time.perf_counter())

    config = PipelineConfig(profiling_enabled=True, profiling_output=str(output / "profiling.json"))
    pipeline = RunPipeline(
        source,
        detector,
        InMemoryReID(ttl_seconds=0),
        analytics,
        lambda crop: np.array([1.0, 0.0]),
        on_event,
        expected_frame_size=(zones.width, zones.height),
        on_frame=on_frame,
        config=config,
    )
    pipeline_holder["pipeline"] = pipeline
    pipeline.set_observability(observability)
    try:
        pipeline.run()
    finally:
        final_memory = _memory_usage()
        if outside_tracing:
            tracemalloc.stop()

    summary = pipeline.profiler.summary()
    elapsed = max(float(summary["elapsed_seconds"]), 1e-9)
    stages = summary["stages"]
    memory_peak = float(final_memory.get("rss_peak_mb") or final_memory["tracemalloc_peak_mb"])
    growth = memory_growth_mb_per_hour(initial_memory, final_memory, elapsed)
    startup_ms = (first_frame.get("at", time.perf_counter()) - build_started) * 1000
    telemetry = observability.snapshot()
    selected_histograms = {
        name: telemetry["histograms"][name]
        for name in (
            "vision_core_inference_latency_ms",
            "vision_core_reid_latency_ms",
            "vision_core_frame_processing_duration_ms",
        )
        if name in telemetry["histograms"]
    }
    return {
        "scenario": scenario,
        "device": device,
        "context": context,
        "frames": int(summary["frames"]),
        "elapsed_seconds": round(elapsed, 6),
        "fps": float(summary["fps"]),
        "frame_p50_ms": stages["frame_total"]["p50_ms"],
        "frame_p95_ms": stages["frame_total"]["p95_ms"],
        "inference_p50_ms": stages["detection"]["p50_ms"],
        "inference_p95_ms": stages["detection"]["p95_ms"],
        "serialization_p95_ms": stages["serialization"]["p95_ms"],
        "startup_ms": round(startup_ms, 4),
        "reconnect_ms": reconnect_ms,
        "memory_peak_mb": round(memory_peak, 3),
        "memory_peak_tracemalloc_mb": round(float(final_memory["tracemalloc_peak_mb"]), 3),
        "memory_growth_mb_per_hour": round(growth, 3),
        "memory": {"initial": initial_memory, "final": final_memory},
        "event_counts": dict(sorted(event_counts.items())),
        "events": sum(event_counts.values()),
        "video": {
            "path": str(video_path),
            "width": zones.width,
            "height": zones.height,
        },
        "environment": environment_metadata(device=device, detector="SyntheticDetector"),
        "profiler": summary,
        "telemetry": {
            "counters": telemetry["counters"],
            "histograms": selected_histograms,
        },
    }


def evaluate_budgets(metrics: dict[str, Any], budgets: dict[str, Any], scenario: str) -> list[dict[str, Any]]:
    config = budgets.get("scenarios", {}).get(scenario)
    if config is None:
        raise ValueError(f"Escenario de presupuestos desconocido: {scenario}")
    violations = []
    for metric, (key, direction) in BUDGET_RULES.items():
        limit = config.get(key)
        actual = metrics.get(metric)
        if limit is None or actual is None:
            continue
        acceptable = actual >= limit if direction == "min" else actual <= limit
        if not acceptable:
            violations.append(
                {
                    "metric": metric,
                    "actual": actual,
                    "limit": limit,
                    "direction": direction,
                }
            )
    return violations


def compare_baseline(
    metrics: dict[str, Any],
    baseline: dict[str, Any],
    tolerance_pct: float = 10.0,
) -> list[dict[str, Any]]:
    previous_metrics = baseline.get("metrics", baseline)
    regressions = []
    for metric, direction in REGRESSION_RULES.items():
        current = metrics.get(metric)
        previous = previous_metrics.get(metric)
        if current is None or previous is None:
            continue
        factor = tolerance_pct / 100
        if direction == "min":
            threshold = float(previous) * (1 - factor)
            degraded = current < threshold
        else:
            floor = 10.0 if metric == "memory_growth_mb_per_hour" else 1.0
            threshold = max(float(previous) * (1 + factor), floor if metric.startswith("memory") else 0.0)
            degraded = current > threshold
        if degraded:
            change = (float(current) - float(previous)) / float(previous) * 100 if previous else 0.0
            regressions.append(
                {
                    "metric": metric,
                    "baseline": previous,
                    "current": current,
                    "threshold": round(threshold, 3),
                    "change_pct": round(change, 2),
                    "direction": direction,
                }
            )
    return regressions


def flatten_metrics(
    metrics: dict[str, Any],
    violations: list[dict[str, Any]],
    regressions: list[dict[str, Any]],
) -> dict[str, Any]:
    flat = {
        key: value
        for key, value in metrics.items()
        if isinstance(value, (str, int, float)) and not isinstance(value, bool)
    }
    for key, value in metrics["environment"].items():
        flat[f"environment_{key}"] = value
    for key, value in metrics["event_counts"].items():
        flat[f"event_{key}"] = value
    flat["budget_violations"] = len(violations)
    flat["regressions"] = len(regressions)
    return flat


def render_summary(
    metrics: dict[str, Any],
    violations: list[dict[str, Any]],
    regressions: list[dict[str, Any]],
    budgets: dict[str, Any],
) -> str:
    scenario = metrics["scenario"]
    config = budgets.get("scenarios", {}).get(scenario, {})
    violated = {item["metric"] for item in violations}
    lines = [
        f"# Benchmark {scenario}",
        "",
        f"- Dispositivo declarado: `{metrics['device']}`",
        f"- Frames: {metrics['frames']} en {metrics['elapsed_seconds']:.3f} s",
        f"- Memoria: {metrics['memory']['final']['source']} (pico {metrics['memory_peak_mb']:.1f} MB)",
        "",
        "| Métrica | Valor | Presupuesto | Estado |",
        "|---|---:|---:|---|",
    ]
    for metric, (key, direction) in BUDGET_RULES.items():
        if metric not in metrics or key not in config:
            continue
        symbol = ">=" if direction == "min" else "<="
        status = "FAIL" if metric in violated else "OK"
        lines.append(f"| {METRIC_LABELS[metric]} | {metrics[metric]:.2f} | {symbol} {config[key]} | {status} |")

    lines.extend(["", "## Hotspots por p95", ""])
    stages = metrics["profiler"]["stages"]
    ranked = sorted(
        ((name, data) for name, data in stages.items() if name != "frame_total" and data["samples"]),
        key=lambda item: item[1]["p95_ms"],
        reverse=True,
    )
    if ranked:
        for name, data in ranked:
            label = HOTSPOT_LABELS.get(name, name)
            lines.append(f"- {label}: p95 {data['p95_ms']:.3f} ms, max {data['max_ms']:.3f} ms")
    else:
        lines.append("- Sin muestras de etapas")

    lines.extend(["", "## Regresión contra baseline", ""])
    if regressions:
        for item in regressions:
            lines.append(
                f"- {METRIC_LABELS.get(item['metric'], item['metric'])}: "
                f"{item['current']} vs baseline {item['baseline']} "
                f"({item['change_pct']:+.2f}%, umbral {item['threshold']})"
            )
    else:
        lines.append("- Sin regresiones o baseline no disponible")

    lines.extend(
        [
            "",
            "Los resultados dependen del hardware del runner y del detector usado.",
            "Consulta [presupuestos y hotspots](docs/performance.md) antes de ajustar umbrales.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _write_csv(path: Path, flat: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted(flat)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(flat)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", default="synthetic-cpu-320x240")
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--zones", type=Path, required=True)
    parser.add_argument("--scene", type=Path, required=True)
    parser.add_argument("--budgets", type=Path, default=Path("benchmarks/budgets.json"))
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--write-baseline", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--csv")
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--device", choices=("cpu", "gpu"), default="cpu")
    parser.add_argument("--confirmation-frames", type=int, default=2)
    parser.add_argument("--fail-on-budget", action="store_true")
    parser.add_argument("--fail-on-regression", action="store_true")
    args = parser.parse_args()

    for path in (args.video, args.zones, args.scene, args.budgets):
        if not path.is_file():
            parser.error(f"No existe el archivo: {path}")
    if args.confirmation_frames < 1:
        parser.error("--confirmation-frames debe ser positivo")

    budgets = load_budgets(args.budgets)
    scenario_config = budgets.get("scenarios", {}).get(args.scenario)
    if scenario_config is None:
        parser.error(f"Escenario desconocido en {args.budgets}: {args.scenario}")

    scene = json.loads(args.scene.read_text(encoding="utf-8"))
    entries = scene.get("entries", [])
    if not entries:
        parser.error("El scene del video sintético no tiene entradas")
    detector = SyntheticDetector(
        [int(entry["track_id"]) for entry in entries],
        [[int(value) for value in entry["lost_ids"]] for entry in entries],
        int(scene.get("width", 0)),
    )
    zones = load_zones(args.zones)
    metrics = run_benchmark(
        source=FileVideoSource(args.video),
        zones=zones,
        detector=detector,
        video_path=args.video,
        output_dir=Path("benchmark-data") / args.scenario,
        scenario=args.scenario,
        device=args.device,
        confirmation_frames=args.confirmation_frames,
        context="nightly",
    )
    if metrics["frames"] < int(scene["frames"]) * 0.9:
        parser.error(f"El pipeline solo procesó {metrics['frames']} de {scene['frames']} frames")

    violations = evaluate_budgets(metrics, budgets, args.scenario)
    tolerance = float(scenario_config.get("regression_tolerance_pct", 10.0))
    baseline = json.loads(args.baseline.read_text(encoding="utf-8")) if args.baseline else None
    regressions = compare_baseline(metrics, baseline, tolerance) if baseline else []
    if args.baseline is None and args.fail_on_regression:
        print("Sin baseline: solo se evalúan presupuestos")

    slug = args.scenario.replace("/", "-")
    output = args.output or Path(f"benchmark-{slug}.json")
    csv_path = Path(args.csv) if args.csv else output.with_suffix(".csv")
    summary_path = args.summary or output.with_suffix(".md")
    summary = render_summary(metrics, violations, regressions, budgets)

    if args.write_baseline:
        _write_json(
            args.write_baseline,
            {
                "schema_version": 1,
                "kind": "baseline",
                "scenario": args.scenario,
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "environment": metrics["environment"],
                "metrics": metrics,
            },
        )
    _write_json(output, {**metrics, "budgets": violations, "regressions": regressions})
    _write_csv(csv_path, flatten_metrics(metrics, violations, regressions))
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(summary, encoding="utf-8")
    print(summary)

    failed = bool((args.fail_on_budget and violations) or (args.fail_on_regression and regressions))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
