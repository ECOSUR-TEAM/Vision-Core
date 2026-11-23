"""Genera el artefacto de resultados de simulacros de incidentes de ECM-104."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from vision_core.core.operations.incident_drills import render_incident_drills, run_incident_drills
from vision_core.core.operations.slo import ROOT, load_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "slo.json")
    parser.add_argument("--timings", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports")
    args = parser.parse_args()

    timings = load_json(args.timings) if args.timings else None
    report = run_incident_drills(load_json(args.config), timings=timings, root=ROOT)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "incident-drills.json"
    markdown_path = args.output_dir / "incident-drills.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    markdown_path.write_text(render_incident_drills(report), encoding="utf-8")

    summary = report["summary"]
    print(f"Simulacros: {summary['passed']}/{summary['total']} correctos · {json_path} · {markdown_path}")
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
