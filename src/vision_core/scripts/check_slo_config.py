"""Verifica que las alertas de ECM-104 tengan SLO, umbral y runbook asociados."""

from __future__ import annotations

import argparse
from pathlib import Path

from vision_core.core.operations.slo import ROOT, load_json, validate_slo_config


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "slo.json")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--metrics-json", type=Path, default=None)
    args = parser.parse_args()

    try:
        config = load_json(args.config)
        metrics = load_json(args.metrics_json) if args.metrics_json else None
    except (OSError, ValueError) as exc:
        print(f"ERROR: no se puede leer la configuración: {exc}")
        return 1

    errors = validate_slo_config(
        config,
        root=args.root,
        budgets_path=args.root / "benchmarks" / "budgets.json",
        metrics_snapshot=metrics,
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print("OK: configuración de SLOs y alertas válida")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
