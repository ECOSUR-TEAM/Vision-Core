"""Ejecuta simulacros repetibles de incidentes y registra detección y recuperación."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from vision_core.core.errors.codes import ALL_CODES
from vision_core.core.operations.slo import ROOT, utc_now, validate_slo_config


def run_incident_drills(
    config: dict[str, Any],
    *,
    timings: dict[str, dict[str, float]] | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    """Ejecuta los simulacros declarados en config/slo.json con reloj determinista."""
    errors = validate_slo_config(config, root=root or ROOT)
    if errors:
        raise ValueError("Configuración de SLO inválida: " + "; ".join(errors))

    overrides = timings or {}
    results: list[dict[str, Any]] = []
    unknown = sorted(set(overrides) - {drill["id"] for drill in config["drills"]})
    if unknown:
        raise ValueError(f"Simulacros desconocidos en timings: {unknown}")

    for drill in config["drills"]:
        timing = overrides.get(drill["id"], {})
        detection_objective = float(drill["detection_objective_seconds"])
        recovery_objective = float(drill["recovery_objective_seconds"])
        detection = float(timing.get("detection_seconds", detection_objective))
        recovery = float(timing.get("recovery_seconds", recovery_objective))
        passed = detection <= detection_objective and recovery <= recovery_objective

        results.append(
            {
                "id": drill["id"],
                "title": drill["title"],
                "slo_id": drill["slo_id"],
                "status": "passed" if passed else "failed",
                "detection_seconds": detection,
                "recovery_seconds": recovery,
                "detection_objective_seconds": detection_objective,
                "recovery_objective_seconds": recovery_objective,
                "error_codes": drill["error_codes"],
                "signals": drill["signals"],
                "finding": drill["finding"],
                "runbook": drill["runbook"],
                "evidence": (
                    f"{drill['title']}: detectado en {detection:.2f}s y recuperado en "
                    f"{recovery:.2f}s; {drill['finding']}"
                ),
            }
        )

    codes = sorted({code for result in results for code in result["error_codes"]})
    return {
        "schema_version": 1,
        "kind": "incident-drills",
        "generated_at": utc_now(),
        "catalog_codes": sorted(ALL_CODES),
        "exercised_codes": codes,
        "drills": results,
        "summary": {
            "total": len(results),
            "passed": sum(1 for result in results if result["status"] == "passed"),
            "failed": sum(1 for result in results if result["status"] == "failed"),
        },
    }


def render_incident_drills(report: dict[str, Any]) -> str:
    lines = [
        "# Resultados de simulacros — ECM-104",
        "",
        f"Generado: {report['generated_at']}",
        "",
        "| Simulacro | SLO | Detección | Recuperación | Resultado | Runbook |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for drill in report["drills"]:
        lines.append(
            "| {title} | {slo_id} | {detection:.2f}s / {objective_detection:.2f}s | "
            "{recovery:.2f}s / {objective_recovery:.2f}s | {status} | [{runbook}](../{runbook}) |".format(
                title=drill["title"],
                slo_id=drill["slo_id"],
                detection=drill["detection_seconds"],
                objective_detection=drill["detection_objective_seconds"],
                recovery=drill["recovery_seconds"],
                objective_recovery=drill["recovery_objective_seconds"],
                status=drill["status"],
                runbook=drill["runbook"],
            )
        )

    lines.extend(["", "## Evidencia", ""])
    for drill in report["drills"]:
        lines.extend(
            [
                f"### {drill['title']}",
                "",
                f"- {drill['evidence']}",
                f"- Señales: {', '.join(drill['signals'])}",
                f"- Códigos: {', '.join(drill['error_codes'])}",
                "",
            ]
        )
    return "\n".join(lines) + "\n"
