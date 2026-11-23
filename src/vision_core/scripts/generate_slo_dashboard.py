"""Genera el tablero de SLO de ECM-104 desde métricas, salud y simulacros."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from vision_core.core.operations.slo import (
    ROOT,
    build_slo_report,
    load_json,
    render_slo_dashboard,
)
from vision_core.core.telemetry.health import HealthStatus
from vision_core.core.telemetry.metrics import ObservabilityMetrics


def _smoke_snapshot() -> dict[str, Any]:
    metrics = ObservabilityMetrics()
    for value in (8, 11, 14, 18, 25, 42, 60):
        metrics.observe("vision_core_frame_processing_duration_ms", value)
    metrics.increment("vision_core_events_emitted_total", 120)
    metrics.increment("vision_core_errors_total", 1)
    metrics.set_gauge("vision_core_fps", 15.0)

    health = HealthStatus(disk_path=str(ROOT))
    health.set_ready(config_valid=True, model_loaded=True, source_connected=True)

    return {
        "metrics": metrics.snapshot(),
        "health": health.snapshot(),
        "state": {"age_seconds": 0.8, "persistence": {"failures": 1}},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "slo.json")
    parser.add_argument("--snapshot-json", type=Path, default=None)
    parser.add_argument("--drills", type=Path, default=ROOT / "reports" / "incident-drills.json")
    parser.add_argument("--history", type=Path, default=ROOT / "reports" / "slo-history.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports")
    args = parser.parse_args()

    snapshot = load_json(args.snapshot_json) if args.snapshot_json else _smoke_snapshot()
    drill_results = load_json(args.drills) if args.drills.is_file() else None
    previous: dict[str, float] = {}
    if args.history.is_file():
        previous = {
            entry["id"]: entry["current"]
            for entry in load_json(args.history).get("slos", [])
            if entry.get("current") is not None
        }

    report = build_slo_report(
        load_json(args.config),
        metrics_snapshot=snapshot["metrics"],
        health_snapshot=snapshot["health"],
        state_snapshot=snapshot["state"],
        drill_results=drill_results,
        previous=previous,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "slo-dashboard.json"
    markdown_path = args.output_dir / "slo-dashboard.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    markdown_path.write_text(render_slo_dashboard(report), encoding="utf-8")
    args.history.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    summary = report["summary"]
    print(f"SLOs: {summary['ok']}/{summary['total']} dentro de objetivo · {json_path} · {markdown_path}")
    return 0 if summary["breach"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
