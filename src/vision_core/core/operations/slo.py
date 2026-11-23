"""Valida configuración de SLOs y construye el tablero operativo de ECM-104."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vision_core.core.errors.codes import ALL_CODES

ROOT = Path(__file__).resolve().parents[4]
DEFAULT_SLO_CONFIG = ROOT / "config" / "slo.json"
DEFAULT_BUDGETS = ROOT / "benchmarks" / "budgets.json"

_SEVERITIES = {"critical", "warning", "info"}
_COMPARISONS = {"gte", "lte"}
_UNITS = {"ratio", "seconds", "ms"}
QUALITY_REASONS = {
    "RESOLUTION_MISMATCH",
    "ZONES_STALE",
    "FROZEN_FRAME",
    "BLURRY_FRAME",
    "EXPOSURE_OUT_OF_RANGE",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def finite_float(value: object) -> float | None:
    """Convierte números JSON a float finito, sin aceptar booleanos ni texto."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _known_codes(values: object, allowed: set[str]) -> list[str]:
    if not isinstance(values, list):
        return []
    return sorted({value for value in values if isinstance(value, str) and value not in allowed})


def validate_slo_config(
    config: dict[str, Any],
    *,
    root: Path | None = None,
    budgets_path: Path | None = None,
    metrics_snapshot: dict[str, Any] | None = None,
) -> list[str]:
    """Devuelve errores de configuración; vacío significa configuración válida."""
    if not isinstance(config, dict):
        return ["config debe ser un objeto JSON"]

    base = root or ROOT
    errors: list[str] = []

    window = config.get("window")
    if not isinstance(window, str) or not window.strip():
        errors.append("window debe ser una cadena no vacía")
    if config.get("schema_version") != 1:
        errors.append("schema_version debe ser 1")
    if config.get("kind") != "slo-dashboard":
        errors.append("kind debe ser 'slo-dashboard'")

    p95_budget: float | None = None
    budgets_file = budgets_path or DEFAULT_BUDGETS
    if budgets_file.is_file():
        try:
            budgets = load_json(budgets_file)
        except (OSError, ValueError) as error:
            errors.append(f"no se puede leer {budgets_file}: {error}")
        else:
            baseline = _as_dict(_as_dict(budgets.get("scenarios")).get("synthetic-cpu-320x240"))
            p95_budget = finite_float(baseline.get("frame_p95_max_ms"))

    slos = config.get("slos")
    if not isinstance(slos, list) or not slos:
        errors.append("slos debe ser una lista no vacía")
        return errors

    slo_ids: set[str] = set()
    alert_ids: set[str] = set()
    by_id: dict[str, dict[str, Any]] = {}

    for index, slo in enumerate(slos):
        label = f"slos[{index}]"
        if not isinstance(slo, dict):
            errors.append(f"{label} debe ser un objeto")
            continue
        slo_id = slo.get("id")
        if not isinstance(slo_id, str) or not slo_id:
            errors.append(f"{label}.id es obligatorio")
            continue
        if slo_id in slo_ids:
            errors.append(f"SLO duplicado: {slo_id}")
        slo_ids.add(slo_id)
        by_id[slo_id] = slo

        objective = finite_float(slo.get("objective"))
        if objective is None or objective <= 0:
            errors.append(f"{label}.objective debe ser un número finito positivo")
        unit = slo.get("unit")
        if unit not in _UNITS:
            errors.append(f"{label}.unit debe ser ratio, seconds o ms")
        if unit == "ratio" and objective is not None and objective > 1:
            errors.append(f"{label}.objective no puede superar 1 para unit=ratio")

        if slo.get("comparison") not in _COMPARISONS:
            errors.append(f"{label}.comparison debe ser 'gte' o 'lte'")

        for field in ("signals", "metrics", "error_codes"):
            values = slo.get(field)
            if not isinstance(values, list) or not values:
                errors.append(f"{label}.{field} debe ser una lista no vacía")
            elif any(not isinstance(value, str) or not value for value in values):
                errors.append(f"{label}.{field} contiene valores inválidos")

        unknown_codes = _known_codes(slo.get("error_codes"), set(ALL_CODES))
        if unknown_codes:
            errors.append(f"{label}.error_codes desconocidos: {unknown_codes}")

        if slo_id == "processing_p95" and p95_budget is not None:
            if objective is not None and objective > p95_budget:
                errors.append("processing_p95.objective excede frame_p95_max_ms de synthetic-cpu-320x240")
            if metrics_snapshot is not None:
                histogram = _as_dict(
                    _as_dict(metrics_snapshot.get("histograms")).get("vision_core_frame_processing_duration_ms")
                )
                current_p95 = finite_float(histogram.get("p95"))
                if current_p95 is not None and current_p95 > p95_budget:
                    errors.append(f"processing_p95 observado {current_p95}ms excede el presupuesto {p95_budget}ms")

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
        if not isinstance(drill, dict):
            errors.append(f"{label} debe ser un objeto")
            continue
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
            value = finite_float(drill.get(field))
            if value is None or value <= 0:
                errors.append(f"{label}.{field} debe ser un número finito positivo")

        unknown_codes = _known_codes(drill.get("error_codes"), set(ALL_CODES) | QUALITY_REASONS)
        if unknown_codes:
            errors.append(f"{label}.error_codes desconocidos: {unknown_codes}")

        runbook = drill.get("runbook")
        if not isinstance(runbook, str) or not runbook.startswith("docs/runbooks/"):
            errors.append(f"{label}.runbook debe apuntar a docs/runbooks/")
        elif not (base / runbook).is_file():
            errors.append(f"{label}.runbook no existe: {runbook}")

        finding = drill.get("finding")
        if not isinstance(finding, str) or not finding.strip():
            errors.append(f"{label}.finding es obligatorio")

    return errors


def _counter_total(counters: dict[str, Any], metric: str) -> float:
    if metric in counters:
        return float(counters[metric])
    return sum(float(value) for key, value in counters.items() if key.startswith(f"{metric}{{"))


def _current_value(
    slo: dict[str, Any],
    *,
    metrics_snapshot: dict[str, Any],
    health_snapshot: dict[str, Any],
    state_snapshot: dict[str, Any],
    drill_results: dict[str, Any] | None,
) -> float | None:
    slo_id = slo["id"]
    counters = _as_dict(metrics_snapshot.get("counters"))
    histograms = _as_dict(metrics_snapshot.get("histograms"))
    gauges = _as_dict(metrics_snapshot.get("gauges"))
    health = _as_dict(health_snapshot)
    state = _as_dict(state_snapshot)

    if slo_id == "monitor_availability":
        return 1.0 if health.get("ready") else 0.0

    if slo_id == "frame_freshness":
        return finite_float(state.get("age_seconds"))

    if slo_id == "processing_p95":
        histogram = _as_dict(histograms.get("vision_core_frame_processing_duration_ms"))
        if finite_float(histogram.get("count")) in (None, 0):
            return None
        return finite_float(histogram.get("p95"))

    if slo_id == "event_delivery":
        attempts = _counter_total(counters, "vision_core_events_emitted_total")
        persistence = _as_dict(state.get("persistence"))
        failures = finite_float(persistence.get("failures")) or 0.0
        if attempts <= 0:
            return None
        failures = min(max(failures, 0.0), attempts)
        return (attempts - failures) / attempts

    if slo_id == "camera_recovery":
        return finite_float(gauges.get("vision_core_camera_recovery_seconds"))

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
    unit: str,
) -> str:
    current_value = finite_float(current)
    previous_value = finite_float(previous)
    if current_value is None or previous_value is None:
        return "sin_datos_previos"
    delta = current_value - previous_value
    tolerance = 0.0005 if unit == "ratio" else max(0.01, abs(previous_value) * 0.01)
    if abs(delta) <= tolerance:
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
    source: str = "snapshot",
) -> dict[str, Any]:
    """Construye el tablero con estado actual, tendencia y umbral de alerta."""
    previous = previous or {}
    entries: list[dict[str, Any]] = []

    for slo in config.get("slos", []):
        if not isinstance(slo, dict):
            continue
        objective = finite_float(slo.get("objective"))
        if objective is None:
            continue
        current = _current_value(
            slo,
            metrics_snapshot=metrics_snapshot,
            health_snapshot=health_snapshot,
            state_snapshot=state_snapshot,
            drill_results=drill_results,
        )
        comparison = slo["comparison"]
        unit = slo["unit"]
        status = "sin_datos"
        if current is not None:
            status = "ok" if _meets(objective, current, comparison) else "brecha"

        entries.append(
            {
                "id": slo["id"],
                "title": slo["title"],
                "objective": objective,
                "comparison": comparison,
                "unit": unit,
                "current": current,
                "status": status,
                "trend": _trend(
                    current=current,
                    previous=previous.get(slo["id"]),
                    comparison=comparison,
                    unit=unit,
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
        "source": source,
        "window": config.get("window", "snapshot"),
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
        f"Generado: {report['generated_at']} · Ventana: {report['window']} · Fuente: {report['source']}",
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

    lines.extend(["", "## Señales y códigos asociados", ""])
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

    no_data = report["summary"]["no_data"]
    if no_data:
        lines.extend([f"> {no_data} SLO sin datos: el tablero no los cuenta como correctos.", ""])
    return "\n".join(lines) + "\n"
