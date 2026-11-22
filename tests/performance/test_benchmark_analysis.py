"""Pruebas de presupuestos, regresiones y reproducibilidad del benchmark."""

import json
from pathlib import Path

import pytest

from vision_core.scripts.benchmark_nightly import (
    compare_baseline,
    evaluate_budgets,
    load_budgets,
    memory_growth_mb_per_hour,
    render_summary,
)

ROOT = Path(__file__).resolve().parents[2]
BUDGETS = ROOT / "benchmarks" / "budgets.json"
BASELINE = ROOT / "benchmarks" / "baseline-synthetic-cpu-320x240.json"
SCENARIO = "synthetic-cpu-320x240"


def _baseline():
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def test_budgets_and_baseline_are_tracked():
    budgets = load_budgets(BUDGETS)
    baseline = _baseline()
    assert budgets["schema_version"] == 1
    assert SCENARIO in budgets["scenarios"]
    assert baseline["kind"] == "baseline"
    assert baseline["metrics"]["scenario"] == SCENARIO
    assert baseline["metrics"]["frames"] == 450
    assert "memory_peak_tracemalloc_mb" in baseline["metrics"]


def test_growth_uses_tracemalloc_and_clamps_short_runs():
    initial = {"tracemalloc_current_mb": 10.0, "rss_current_mb": 50.0}
    final = {"tracemalloc_current_mb": 12.0, "rss_current_mb": 500.0}
    assert memory_growth_mb_per_hour(initial, final, 1.0) == 240.0
    assert memory_growth_mb_per_hour(initial, final, 60.0) == 120.0


def test_evaluate_budgets_flags_degraded_metrics():
    metrics = dict(_baseline()["metrics"])
    metrics["fps"] = 5.0
    metrics["frame_p95_ms"] = 500.0
    violations = evaluate_budgets(metrics, load_budgets(BUDGETS), SCENARIO)
    assert {item["metric"] for item in violations} >= {"fps", "frame_p95_ms"}
    assert all(item["direction"] in {"min", "max"} for item in violations)


def test_compare_baseline_detects_artificial_regression():
    baseline = _baseline()
    current = dict(baseline["metrics"])
    current["fps"] = baseline["metrics"]["fps"] * 0.5
    current["frame_p95_ms"] = baseline["metrics"]["frame_p95_ms"] * 2
    regressions = compare_baseline(current, baseline, tolerance_pct=10.0)
    assert {item["metric"] for item in regressions} == {"fps", "frame_p95_ms"}
    assert all(item["change_pct"] != 0 for item in regressions)


def test_compare_baseline_ignores_normal_fluctuation():
    baseline = _baseline()
    current = dict(baseline["metrics"])
    current["fps"] = baseline["metrics"]["fps"] * 0.99
    current["frame_p95_ms"] = baseline["metrics"]["frame_p95_ms"] * 1.02
    assert compare_baseline(current, baseline, tolerance_pct=10.0) == []


def test_compare_baseline_ignores_runner_sensitive_timing():
    baseline = _baseline()
    current = dict(baseline["metrics"])
    current["startup_ms"] = baseline["metrics"]["startup_ms"] * 3
    current["reconnect_ms"] = baseline["metrics"]["reconnect_ms"] * 3
    assert compare_baseline(current, baseline, tolerance_pct=10.0) == []

    metrics = dict(current)
    metrics["startup_ms"] = 40_000.0
    violations = {item["metric"] for item in evaluate_budgets(metrics, load_budgets(BUDGETS), SCENARIO)}
    assert "startup_ms" in violations


def test_compare_baseline_uses_tracemalloc_peak_across_sources():
    baseline = _baseline()
    comparable = baseline["metrics"]["memory_peak_tracemalloc_mb"]
    current = dict(baseline["metrics"])
    current["memory_peak_mb"] = 68.5
    current["memory_peak_tracemalloc_mb"] = comparable * 1.01
    metrics = {item["metric"] for item in compare_baseline(current, baseline, tolerance_pct=10.0)}
    assert "memory_peak_mb" not in metrics
    assert "memory_peak_tracemalloc_mb" not in metrics

    current["memory_peak_tracemalloc_mb"] = comparable * 2
    metrics = {item["metric"] for item in compare_baseline(current, baseline, tolerance_pct=10.0)}
    assert "memory_peak_tracemalloc_mb" in metrics


def test_summary_renders_hotspots_and_budget_status():
    metrics = _baseline()["metrics"]
    summary = render_summary(metrics, [], [], load_budgets(BUDGETS))
    assert "| FPS |" in summary
    assert "captura/decode" in summary
    assert "serialización" in summary
    assert "Sin regresiones" in summary


def test_unknown_scenario_raises_value_error():
    with pytest.raises(ValueError, match="Escenario de presupuestos desconocido"):
        evaluate_budgets(_baseline()["metrics"], load_budgets(BUDGETS), "no-existe")
