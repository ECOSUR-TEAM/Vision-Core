"""Valida configuración de SLOs y construye el tablero operativo de ECM-104."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vision_core.core.errors.codes import ALL_CODES

ROOT = Path(__file__).resolve().parents[4]
DEFAULT_SLO_CONFIG = ROOT / "config" / "slo.json"
DEFAULT_BUDGETS = ROOT / "benchmarks" / "budgets.json"

_SEVERITIES = {"critical", "warning", "info"}
_COMPARISONS = {"gte", "lte"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def validate_slo_config(
    config: dict[str, Any],
    *,
    root: Path | None = None,
    budgets_path: Path | None = None,
) -> list[str]:
    """Devuelve errores de configuración; vacío significa configuración válida."""
    base = root or ROOT
    errors: list[str] = []

    if config.get("schema_version") != 1:
        errors.append("schema_version debe ser 1")
    if config.get("kind") != "slo-dashboard":
        errors.append("kind debe ser 'slo-dashboard'")

    slos = config.get("slos")
    if not isinstance(slos, list) or not slos:
        errors.append("slos debe ser una lista no vacía")
        return errors

    slo_ids: set[str] = set()
    alert_ids: set[str] = set()
    by_id: dict[str, dict[str, Any]] = {}

    for index, slo in enumerate(slos):
        label = f"slos[{index}]"
        slo_id = slo.get("id")
        if not isinstance(slo_id, str) or not slo_id:
            errors.append(f"{label}.id es obligatorio")
            continue
        if slo_id in slo_ids:
            errors.append(f"SLO duplicado: {slo_id}")
        slo_ids.add(slo_id)
        by_id[slo_id] = slo

        objective = slo.get("objective")
        if not isinstance(objective, (int, float)) or isinstance(objective, bool) or objective <= 0:
            errors.append(f"{label}.objective debe ser un número positivo")

        if slo.get("unit") == "ratio" and isinstance(objective, (int, float)) and objective > 1:
            errors.append(f"{label}.objective no puede superar 1 para unit=ratio")

        if slo.get("comparison") not in _COMPARISONS:
            errors.append(f"{label}.comparison debe ser 'gte' o 'lte'")

        for field in ("signals", "metrics", "error_codes"):
            values = slo.get(field)
            if not isinstance(values, list) or not values:
                errors.append(f"{label}.{field} debe ser una lista no vacía")
                continue
            if any(not isinstance(value, str) or not value for value in values):
                errors.append(f"{label}.{field} contiene valores inválidos")

        unknown_codes = sorted(set(slo.get("error_codes", [])) - set(ALL_CODES))
        if unknown_codes:
            errors.append(f"{label}.error_codes desconocidos: {unknown_codes}")

        alert = slo.get("alert")
        if not isinstance(alert, dict):
            errors.append(f"{label}.alert es obligatorio")
            continue

        alert_id = alert.get("id")
        if not isinstance(alert_id, str) or not alert_id:
            errors.append(f"{label}.alert.id es obligatorio")
        elif alert_id in alert_ids:
            errors.append(f"Alerta duplicada: {alert_id}")
        else:
            alert_ids.add(alert_id)

        if alert.get("severity") not in _SEVERITIES:
            errors.append(f"{label}.alert.severity debe ser critical, warning o info")

        runbook = alert.get("runbook")
        if not isinstance(runbook, str) or not runbook.startswith("docs/runbooks/"):
            errors.append(f"{label}.alert.runbook debe apuntar a docs/runbooks/")
        elif not (base / runbook).is_file():
            errors.append(f"{label}.alert.runbook no existe: {runbook}")

    drills = config.get("drills")
    if not isinstance(drills, list) or not drills:
        errors.append("drills debe ser una lista no vacía")
        return errors

    drill_ids: set[str] = set()
    for index, drill in enumerate(drills):
        label = f"drills[{index}]"
        drill_id = drill.get("id")
        if not isinstance(drill_id, str) or not drill_id:
            errors.append(f"{label}.id es obligatorio")
            continue
        if drill_id in drill_ids:
            errors.append(f"Simulacro duplicado: {drill_id}")
        drill_ids.add(drill_id)

        if drill.get("slo_id") not in slo_ids:
            errors.append(f"{label}.slo_id no apunta a un SLO: {drill.get('slo_id')}")

        for field in ("detection_objective_seconds", "recovery_objective_seconds"):
            value = drill.get(field)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
                errors.append(f"{label}.{field} debe ser un número positivo")

        unknown_codes = sorted(set(drill.get("error_codes", [])) - set(ALL_CODES))
        if unknown_codes:
            errors.append(f"{label}.error_codes desconocidos: {unknown_codes}")

        runbook = drill.get("runbook")
        if not isinstance(runbook, str) or not runbook.startswith("docs/runbooks/"):
            errors.append(f"{label}.runbook debe apuntar a docs/runbooks/")
        elif not (base / runbook).is_file():
            errors.append(f"{label}.runbook no existe: {runbook}")

        if not isinstance(drill.get("finding"), str) or not drill["finding"].strip():
            errors.append(f"{label}.finding es obligatorio")

    budgets_file = budgets_path or DEFAULT_BUDGETS
    if budgets_file.is_file():
        budgets = load_json(budgets_file)
        baseline = budgets.get("scenarios", {}).get("synthetic-cpu-320x240", {})
        p95_budget = baseline.get("frame_p95_max_ms")
        processing = by_id.get("processing_p95", {})
        objective = processing.get("objective")
        if isinstance(p95_budget, (int, float)) and isinstance(objective, (int, float)):
            if objective > p95_budget:
                errors.append("processing_p95.objective excede frame_p95_max_ms de synthetic-cpu-320x240")

    return errors


def _counter_total(counters: dict[str, Any], metric: str) -> float:
    return sum(float(value) for key, value in counters.items() if key == metric or key.startswith(f"{metric}{{"))


def _current_value(
    slo: dict[str, Any],
    *,
    metrics_snapshot: dict[str, Any],
    health_snapshot: dict[str, Any],
    state_snapshot: dict[str, Any],
    drill_results: dict[str, Any] | None,
) -> float | None:
    slo_id = slo["id"]
    counters = metrics_snapshot.get("counters", {})
    histograms = metrics_snapshot.get("histograms", {})

    if slo_id == "monitor_availability":
        return 1.0 if health_snapshot.get("ready") else 0.0

    if slo_id == "frame_freshness":
        return float(state_snapshot.get("age_seconds", 0.0))

    if slo_id == "processing_p95":
        histogram = histograms.get("vision_core_frame_processing_duration_ms")
        if not isinstance(histogram, dict) or histogram.get("count", 0) == 0:
            return None
        return float(histogram.get("p95", 0.0))

    if slo_id == "event_delivery":
        emitted = _counter_total(counters, "vision_core_events_emitted_total")
        failures = float(state_snapshot.get("persistence", {}).get("failures", 0.0))
        total = emitted + failures
        return emitted / total if total else 1.0

    if slo_id == "camera_recovery":
        if not drill_results:
            return None
        values = [
            float(drill["recovery_seconds"])
            for drill in drill_results.get("drills", [])
            if drill.get("slo_id") == slo_id
        ]
        if not values:
            return None
        ordered = sorted(values)
        middle = len(ordered) // 2
        if len(ordered) % 2 == 0:
            return (ordered[middle - 1] + ordered[middle]) / 2
        return ordered[middle]

    return None


def _meets(objective: float, current: float, comparison: str) -> bool:
    if comparison == "gte":
        return current >= objective
    return current <= objective


def _trend(
    *,
    current: float | None,
    previous: float | None,
    comparison: str,
) -> str:
    if current is None or previous is None:
        return "sin_datos_previos"
    delta = current - previous
    if abs(delta) < 0.01:
        return "estable"
    improving = delta > 0 if comparison == "gte" else delta < 0
    return "mejorando" if improving else "empeorando"


def build_slo_report(
    config: dict[str, Any],
    *,
    metrics_snapshot: dict[str, Any],
    health_snapshot: dict[str, Any],
    state_snapshot: dict[str, Any],
    drill_results: dict[str, Any] | None = None,
    previous: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Construye el tablero con estado actual, tendencia y umbral de alerta."""
    previous = previous or {}
    entries: list[dict[str, Any]] = []

    for slo in config.get("slos", []):
        objective = float(slo["objective"])
        current = _current_value(
            slo,
            metrics_snapshot=metrics_snapshot,
            health_snapshot=health_snapshot,
            state_snapshot=state_snapshot,
            drill_results=drill_results,
        )
        comparison = slo["comparison"]
        status = "sin_datos"
        if current is not None:
            status = "ok" if _meets(objective, current, comparison) else "brecha"

        entries.append(
            {
                "id": slo["id"],
                "title": slo["title"],
                "objective": objective,
                "comparison": comparison,
                "unit": slo["unit"],
                "current": current,
                "status": status,
                "trend": _trend(
                    current=current,
                    previous=previous.get(slo["id"]),
                    comparison=comparison,
                ),
                "signals": slo["signals"],
                "error_codes": slo["error_codes"],
                "alert": slo["alert"],
            }
        )

    return {
        "schema_version": 1,
        "kind": "slo-dashboard",
        "generated_at": utc_now(),
        "window": config.get("window", "24h"),
        "slos": entries,
        "summary": {
            "total": len(entries),
            "ok": sum(1 for entry in entries if entry["status"] == "ok"),
            "breach": sum(1 for entry in entries if entry["status"] == "brecha"),
            "no_data": sum(1 for entry in entries if entry["status"] == "sin_datos"),
        },
    }


def _format_value(entry: dict[str, Any]) -> str:
    if entry["current"] is None:
        return "sin datos"
    if entry["unit"] == "ratio":
        return f"{entry['current']:.2%}"
    return f"{entry['current']:.2f} {entry['unit']}"


def _format_objective(entry: dict[str, Any]) -> str:
    if entry["unit"] == "ratio":
        return f"{entry['objective']:.2%}"
    return f"{entry['objective']:.2f} {entry['unit']}"


def render_slo_dashboard(report: dict[str, Any]) -> str:
    lines = [
        "# Tablero de SLO — ECM-104",
        "",
        f"Generado: {report['generated_at']} · Ventana: {report['window']}",
        "",
        "| SLO | Actual | Umbral | Estado | Tendencia | Alerta | Runbook |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for entry in report["slos"]:
        alert = entry["alert"]
        lines.append(
            "| {title} | {current} | {comparison} {objective} | {status} | {trend} | "
            "{severity} | [{runbook}](../{runbook}) |".format(
                title=entry["title"],
                current=_format_value(entry),
                comparison=">=" if entry["comparison"] == "gte" else "<=",
                objective=_format_objective(entry),
                status=entry["status"],
                trend=entry["trend"],
                severity=alert["severity"],
                runbook=alert["runbook"],
            )
        )

    lines.extend(
        [
            "",
            "## Señales y códigos asociados",
            "",
        ]
    )
    for entry in report["slos"]:
        lines.extend(
            [
                f"### {entry['title']}",
                "",
                f"- Señales: {', '.join(entry['signals'])}",
                f"- Códigos: {', '.join(entry['error_codes'])}",
                f"- Alerta `{entry['alert']['id']}`: `{entry['alert']['severity']}`",
                "",
            ]
        )
    return "\n".join(lines) + "\n"
