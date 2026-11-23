"""Genera el tablero de SLO de ECM-104 desde métricas, salud y simulacros."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from vision_core.core.operations.slo import (
    ROOT,
    build_slo_report,
    finite_float,
    load_json,
    render_slo_dashboard,
    validate_slo_config,
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
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--snapshot-json", type=Path, default=None)
    parser.add_argument("--drills", type=Path, default=None)
    parser.add_argument("--history", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    config_path = args.config or args.root / "config" / "slo.json"
    drills_path = args.drills or args.root / "reports" / "incident-drills.json"
    history_path = args.history or args.root / "reports" / "slo-history.json"
    output_dir = args.output_dir or args.root / "reports"

    try:
        config = load_json(config_path)
        snapshot = load_json(args.snapshot_json) if args.snapshot_json else _smoke_snapshot()
        drill_results = load_json(drills_path) if drills_path.is_file() else None
        errors = validate_slo_config(
            config,
            root=args.root,
            budgets_path=args.root / "benchmarks" / "budgets.json",
            metrics_snapshot=snapshot.get("metrics"),
        )
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1

        previous: dict[str, float] = {}
        if history_path.is_file():
            history = load_json(history_path)
            for entry in history.get("slos", []):
                value = finite_float(entry.get("current"))
                if value is not None:
                    previous[entry["id"]] = value
    except (OSError, ValueError) as error:
        print(f"ERROR: no se puede generar el tablero: {error}")
        return 1

    report = build_slo_report(
        config,
        metrics_snapshot=snapshot.get("metrics", {}),
        health_snapshot=snapshot.get("health", {}),
        state_snapshot=snapshot.get("state", {}),
        drill_results=drill_results,
        previous=previous,
        source="live" if args.snapshot_json else "smoke",
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "slo-dashboard.json"
    markdown_path = output_dir / "slo-dashboard.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    markdown_path.write_text(render_slo_dashboard(report), encoding="utf-8")
    history_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    summary = report["summary"]
    drill_failures = int((drill_results or {}).get("summary", {}).get("failed", 0))
    print(
        f"SLOs: {summary['ok']}/{summary['total']} dentro de objetivo · "
        f"{summary['no_data']} sin datos · {json_path} · {markdown_path}"
    )
    return 0 if summary["breach"] == 0 and drill_failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
