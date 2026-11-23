"""Ejecuta simulacros repetibles de incidentes y registra latencias inyectadas."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from vision_core.core.errors.codes import ALL_CODES
from vision_core.core.operations.slo import (
    QUALITY_REASONS,
    ROOT,
    finite_float,
    utc_now,
    validate_slo_config,
)


def _validate_timings(timings: dict[str, dict[str, float]]) -> None:
    for drill_id, timing in timings.items():
        if not isinstance(timing, dict):
            raise ValueError(f"Timings de simulacro inválidos para {drill_id}")
        for field in ("detection_seconds", "recovery_seconds"):
            if field in timing:
                value = finite_float(timing[field])
                if value is None or value < 0:
                    raise ValueError(f"{drill_id}.{field} debe ser un número finito no negativo")


def run_incident_drills(
    config: dict[str, Any],
    *,
    timings: dict[str, dict[str, float]] | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    """Ejecuta los simulacros declarados en config/slo.json con latencias inyectadas."""
    errors = validate_slo_config(config, root=root or ROOT)
    if errors:
        raise ValueError("Configuración de SLO inválida: " + "; ".join(errors))

    overrides = timings or {}
    _validate_timings(overrides)
    results: list[dict[str, Any]] = []
    unknown = sorted(set(overrides) - {drill["id"] for drill in config["drills"]})
    if unknown:
        raise ValueError(f"Simulacros desconocidos en timings: {unknown}")

    for drill in config["drills"]:
        timing = overrides.get(drill["id"], {})
        detection_objective = finite_float(drill["detection_objective_seconds"])
        recovery_objective = finite_float(drill["recovery_objective_seconds"])
        if detection_objective is None or recovery_objective is None:
            raise ValueError(f"Objetivos inválidos en el simulacro {drill.get('id')}")
        detection_value = finite_float(timing.get("detection_seconds"))
        recovery_value = finite_float(timing.get("recovery_seconds"))
        detection = detection_objective if detection_value is None else detection_value
        recovery = recovery_objective if recovery_value is None else recovery_value
        passed = detection <= detection_objective and recovery <= recovery_objective

        results.append(
            {
                "id": drill["id"],
                "title": drill["title"],
                "slo_id": drill["slo_id"],
                "mode": "synthetic",
                "measured": False,
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
                    f"{drill['title']}: latencia simulada de detección {detection:.2f}s "
                    f"(objetivo {detection_objective:.2f}s) y recuperación {recovery:.2f}s "
                    f"(objetivo {recovery_objective:.2f}s); {drill['finding']}"
                ),
            }
        )

    codes = sorted({code for result in results for code in result["error_codes"]})
    return {
        "schema_version": 1,
        "kind": "incident-drills",
        "mode": "synthetic",
        "generated_at": utc_now(),
        "catalog_codes": sorted(ALL_CODES),
        "quality_reasons": sorted(QUALITY_REASONS),
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
        f"Generado: {report['generated_at']} · Modo: {report['mode']} · Latencias inyectadas, no medidas en producción",
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

    lines.extend(["", "## Evidencia simulada", ""])
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
