"""Tests para SLOs, alertas, tablero y simulacros de ECM-104."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

import pytest

from vision_core.core.errors.codes import ALL_CODES
from vision_core.core.operations.incident_drills import render_incident_drills
from vision_core.core.operations.incident_drills import run_incident_drills as run_drills
from vision_core.core.operations.slo import (
    ROOT,
    _counter_total,
    build_slo_report,
    finite_float,
    load_json,
    render_slo_dashboard,
    validate_slo_config,
)
from vision_core.scripts import check_slo_config, generate_slo_dashboard
from vision_core.scripts import run_incident_drills as drills_script

CONFIG = ROOT / "config" / "slo.json"


def _config() -> dict[str, Any]:
    return load_json(CONFIG)


def _snapshots() -> dict[str, Any]:
    return {
        "metrics": {
            "counters": {
                "vision_core_events_emitted_total": 100.0,
                "vision_core_errors_total": 1.0,
            },
            "gauges": {
                "vision_core_fps": 15.0,
                "vision_core_camera_recovery_seconds": 8.0,
            },
            "histograms": {
                "vision_core_frame_processing_duration_ms": {
                    "count": 10,
                    "p95": 42.0,
                }
            },
        },
        "health": {
            "ready": True,
            "checks": {"model": True, "video_source": True, "disk": True},
        },
        "state": {"age_seconds": 0.5, "persistence": {"failures": 1}},
    }


def _build(snapshots: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    return build_slo_report(
        _config(),
        metrics_snapshot=snapshots["metrics"],
        health_snapshot=snapshots["health"],
        state_snapshot=snapshots["state"],
        **kwargs,
    )


def test_repo_slo_config_is_valid():
    assert validate_slo_config(_config(), root=ROOT) == []


def test_validate_requires_window():
    config = _config()
    del config["window"]

    errors = validate_slo_config(config, root=ROOT)

    assert any("window" in error for error in errors)


def test_validate_handles_malformed_shapes_without_crashing():
    config = cast("dict[str, Any]", [])
    assert "objeto JSON" in validate_slo_config(config, root=ROOT)[0]

    config = _config()
    config["slos"][0] = None
    config["drills"][0] = None

    errors = validate_slo_config(config, root=ROOT)

    assert any("slos[0] debe ser un objeto" in error for error in errors)
    assert any("drills[0] debe ser un objeto" in error for error in errors)


def test_validate_rejects_ratio_objective_above_one():
    config = _config()
    config["slos"][0]["objective"] = 1.5

    errors = validate_slo_config(config, root=ROOT)

    assert any("no puede superar 1" in error for error in errors)


def test_validate_rejects_alert_without_existing_runbook():
    config = _config()
    config["slos"][0]["alert"]["runbook"] = "docs/runbooks/no-existe.md"

    errors = validate_slo_config(config, root=ROOT)

    assert any("no existe" in error for error in errors)


def test_validate_rejects_unknown_error_codes_in_slo():
    config = _config()
    config["slos"][0]["error_codes"].append("FROZEN_FRAME")

    errors = validate_slo_config(config, root=ROOT)

    assert any("desconocidos" in error for error in errors)


def test_validate_accepts_documented_quality_reason_in_drill():
    config = _config()

    assert validate_slo_config(config, root=ROOT) == []
    assert "FROZEN_FRAME" in config["drills"][1]["error_codes"]


def test_validate_rejects_orphan_drill():
    config = _config()
    config["drills"][0]["slo_id"] = "slo_inexistente"

    errors = validate_slo_config(config, root=ROOT)

    assert any("no apunta a un SLO" in error for error in errors)


def test_validate_checks_observed_p95_against_budget():
    snapshots = _snapshots()
    snapshots["metrics"]["histograms"]["vision_core_frame_processing_duration_ms"]["p95"] = 61.0

    errors = validate_slo_config(_config(), root=ROOT, metrics_snapshot=snapshots["metrics"])

    assert any("presupuesto" in error for error in errors)


def test_finite_float_rejects_boolean_and_non_finite_values():
    assert finite_float(3) == 3.0
    assert finite_float(True) is None
    assert finite_float(float("nan")) is None
    assert finite_float("1") is None


def test_counter_total_prefers_base_key():
    counters = {
        "vision_core_events_emitted_total": 10.0,
        "vision_core_events_emitted_total{camera_id=cam}": 10.0,
    }

    assert _counter_total(counters, "vision_core_events_emitted_total") == 10.0


def test_counter_total_sums_labelled_keys_without_base():
    counters = {
        "vision_core_events_emitted_total{camera_id=cam1}": 6.0,
        "vision_core_events_emitted_total{camera_id=cam2}": 4.0,
    }

    assert _counter_total(counters, "vision_core_events_emitted_total") == 10.0


def test_null_snapshot_values_do_not_crash():
    snapshots = _snapshots()
    snapshots["state"] = {"age_seconds": None, "persistence": None}

    report = _build(snapshots)

    freshness = next(item for item in report["slos"] if item["id"] == "frame_freshness")
    delivery = next(item for item in report["slos"] if item["id"] == "event_delivery")
    assert freshness["current"] is None
    assert freshness["status"] == "sin_datos"
    assert delivery["current"] == 1.0


def test_event_delivery_uses_attempts_and_clamps_failures():
    snapshots = _snapshots()
    snapshots["state"]["persistence"]["failures"] = 200

    report = _build(snapshots)

    entry = next(item for item in report["slos"] if item["id"] == "event_delivery")
    assert entry["current"] == 0.0
    assert entry["status"] == "brecha"


def test_event_delivery_without_attempts_has_no_data():
    snapshots = _snapshots()
    snapshots["metrics"]["counters"].pop("vision_core_events_emitted_total")

    report = _build(snapshots)

    entry = next(item for item in report["slos"] if item["id"] == "event_delivery")
    assert entry["current"] is None
    assert entry["status"] == "sin_datos"


def test_camera_recovery_uses_optional_gauge():
    report = _build(_snapshots())

    entry = next(item for item in report["slos"] if item["id"] == "camera_recovery")
    assert entry["current"] == 8.0
    assert entry["status"] == "ok"


def test_camera_recovery_without_gauge_is_no_data():
    snapshots = _snapshots()
    snapshots["metrics"]["gauges"].pop("vision_core_camera_recovery_seconds")

    report = _build(snapshots)

    entry = next(item for item in report["slos"] if item["id"] == "camera_recovery")
    assert entry["current"] is None
    assert entry["status"] == "sin_datos"


def test_build_slo_report_uses_p95_and_marks_breach():
    snapshots = _snapshots()
    snapshots["metrics"]["histograms"]["vision_core_frame_processing_duration_ms"]["p95"] = 90.0

    report = _build(snapshots)
    entry = next(item for item in report["slos"] if item["id"] == "processing_p95")

    assert entry["current"] == 90.0
    assert entry["status"] == "brecha"
    assert entry["trend"] == "sin_datos_previos"


def test_trend_uses_unit_aware_tolerance():
    report = _build(_snapshots(), previous={"event_delivery": 0.99})
    entry = next(item for item in report["slos"] if item["id"] == "event_delivery")

    assert entry["trend"] == "estable"

    snapshots = _snapshots()
    snapshots["metrics"]["counters"]["vision_core_events_emitted_total"] = 1000.0
    snapshots["state"]["persistence"]["failures"] = 0
    report = _build(snapshots, previous={"event_delivery": 0.99})
    entry = next(item for item in report["slos"] if item["id"] == "event_delivery")

    assert entry["trend"] == "mejorando"


def test_render_dashboard_links_each_alert_runbook():
    report = _build(_snapshots())
    markdown = render_slo_dashboard(report)

    assert markdown.count("../docs/runbooks/") == 5
    assert "critical" in markdown
    assert "warning" in markdown
    assert "Fuente: snapshot" in markdown


def test_run_drills_records_all_scenarios():
    report = run_drills(_config(), root=ROOT)

    assert report["mode"] == "synthetic"
    assert report["summary"] == {"total": 6, "passed": 6, "failed": 0}
    assert {drill["id"] for drill in report["drills"]} == {
        "rtsp_disconnected",
        "frozen_frame",
        "weights_missing",
        "event_sink_down",
        "disk_full",
        "container_restart",
    }
    assert set(report["exercised_codes"]) <= set(ALL_CODES) | {"FROZEN_FRAME"}
    assert all(drill["measured"] is False for drill in report["drills"])
    assert "detectado en" not in render_incident_drills(report)


def test_run_drills_marks_slow_recovery_as_failed():
    report = run_drills(
        _config(),
        timings={"rtsp_disconnected": {"recovery_seconds": 999.0}},
        root=ROOT,
    )
    drill = next(item for item in report["drills"] if item["id"] == "rtsp_disconnected")

    assert drill["status"] == "failed"
    assert report["summary"]["failed"] == 1


def test_run_drills_rejects_invalid_timings():
    with pytest.raises(ValueError, match="no negativo"):
        run_drills(
            _config(),
            timings={"rtsp_disconnected": {"recovery_seconds": -1.0}},
            root=ROOT,
        )


def test_check_cli_accepts_repo_config(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    monkeypatch.setattr(sys, "argv", ["check_slo_config"])

    assert check_slo_config.main() == 0
    assert "válida" in capsys.readouterr().out


def test_check_cli_rejects_bad_config(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
):
    config = _config()
    config["schema_version"] = 2
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["check_slo_config", "--config", str(path), "--root", str(ROOT)])

    assert check_slo_config.main() == 1
    assert "schema_version" in capsys.readouterr().out


def test_drills_cli_writes_reports(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_incident_drills", "--root", str(ROOT), "--output-dir", str(tmp_path / "nested")],
    )

    assert drills_script.main() == 0
    assert (tmp_path / "nested" / "incident-drills.json").is_file()
    assert (tmp_path / "nested" / "incident-drills.md").is_file()


def test_drills_cli_fails_on_slow_recovery(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    timings = tmp_path / "timings.json"
    timings.write_text(json.dumps({"rtsp_disconnected": {"recovery_seconds": 999.0}}), encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_incident_drills",
            "--root",
            str(ROOT),
            "--timings",
            str(timings),
            "--output-dir",
            str(tmp_path / "out"),
        ],
    )

    assert drills_script.main() == 1


def test_dashboard_cli_writes_reports_and_history(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate_slo_dashboard",
            "--root",
            str(ROOT),
            "--history",
            str(tmp_path / "history" / "slo-history.json"),
            "--output-dir",
            str(tmp_path / "out"),
        ],
    )

    assert generate_slo_dashboard.main() == 0
    assert (tmp_path / "out" / "slo-dashboard.json").is_file()
    assert (tmp_path / "history" / "slo-history.json").is_file()


def test_dashboard_cli_fails_on_breach(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    config = _config()
    config["slos"][2]["objective"] = 1.0
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate_slo_dashboard",
            "--root",
            str(ROOT),
            "--config",
            str(path),
            "--history",
            str(tmp_path / "slo-history.json"),
            "--output-dir",
            str(tmp_path / "out"),
        ],
    )

    assert generate_slo_dashboard.main() == 1


def test_validate_reports_malformed_slo_fields(tmp_path: Path):
    config = _config()
    budgets = tmp_path / "budgets.json"
    budgets.write_text("{", encoding="utf-8")
    config["kind"] = "otro"
    config["slos"][0]["id"] = ""
    config["slos"][1]["objective"] = 0
    config["slos"][1]["unit"] = "horas"
    config["slos"][1]["comparison"] = "equals"
    config["slos"][1]["error_codes"] = None
    config["slos"][1]["signals"] = None
    config["slos"][1]["metrics"] = [""]
    config["slos"][1]["alert"] = None
    config["slos"][2]["id"] = config["slos"][3]["id"]
    config["slos"][2]["alert"]["id"] = ""
    config["slos"][3]["alert"]["id"] = "alerta-duplicada"
    config["slos"][4]["alert"]["id"] = "alerta-duplicada"
    config["slos"][4]["alert"]["severity"] = "urgent"
    config["slos"][4]["alert"]["runbook"] = "runbook.md"

    errors = validate_slo_config(config, root=ROOT, budgets_path=budgets)

    assert any("kind" in error for error in errors)
    assert any("no se puede leer" in error for error in errors)
    assert any(".id es obligatorio" in error for error in errors)
    assert any("SLO duplicado" in error for error in errors)
    assert any("objective debe ser" in error for error in errors)
    assert any("unit debe ser" in error for error in errors)
    assert any("comparison debe ser" in error for error in errors)
    assert any("error_codes debe ser" in error for error in errors)
    assert any("signals debe ser" in error for error in errors)
    assert any("metrics contiene" in error for error in errors)
    assert any("alert es obligatorio" in error for error in errors)
    assert any("alert.id es obligatorio" in error for error in errors)
    assert any("Alerta duplicada" in error for error in errors)
    assert any("severity debe ser" in error for error in errors)
    assert any("alert.runbook debe apuntar" in error for error in errors)


def test_validate_requires_slos_and_accepts_missing_budget_file(tmp_path: Path):
    config = _config()
    config["slos"] = []

    errors = validate_slo_config(config, root=ROOT, budgets_path=tmp_path / "sin-presupuesto.json")

    assert any("slos debe ser una lista no vacía" in error for error in errors)
    assert validate_slo_config(_config(), root=ROOT, budgets_path=tmp_path / "sin-presupuesto.json") == []


def test_validate_rejects_p95_objective_above_budget():
    config = _config()
    config["slos"][2]["objective"] = 1000.0

    errors = validate_slo_config(config, root=ROOT)

    assert any("excede frame_p95_max_ms" in error for error in errors)


def test_validate_reports_malformed_drill_fields():
    config = _config()
    config["drills"] = []
    empty_errors = validate_slo_config(config, root=ROOT)
    assert any("drills debe ser una lista no vacía" in error for error in empty_errors)

    config = _config()
    config["drills"][0]["id"] = ""
    config["drills"][1]["id"] = config["drills"][2]["id"]
    config["drills"][1]["detection_objective_seconds"] = -1
    config["drills"][1]["error_codes"] = ["FROZEN_FRAME", "NO_EXISTE"]
    config["drills"][2]["runbook"] = "runbook.md"
    config["drills"][3]["finding"] = ""

    errors = validate_slo_config(config, root=ROOT)

    assert any(".id es obligatorio" in error for error in errors)
    assert any("Simulacro duplicado" in error for error in errors)
    assert any("detection_objective_seconds debe ser" in error for error in errors)
    assert any("error_codes desconocidos" in error for error in errors)
    assert any("runbook debe apuntar" in error for error in errors)
    assert any("finding es obligatorio" in error for error in errors)


def test_build_report_skips_malformed_entries_and_handles_unknown_slo():
    snapshots = _snapshots()
    snapshots["metrics"]["histograms"]["vision_core_frame_processing_duration_ms"]["count"] = 0
    config = _config()
    custom = dict(config["slos"][0])
    custom["id"] = "slo_personalizado"
    config["slos"].append(cast("dict[str, Any]", None))
    config["slos"].append({"objective": None})
    config["slos"].append(custom)

    report = build_slo_report(
        config,
        metrics_snapshot=snapshots["metrics"],
        health_snapshot=snapshots["health"],
        state_snapshot=snapshots["state"],
    )

    p95 = next(item for item in report["slos"] if item["id"] == "processing_p95")
    custom = next(item for item in report["slos"] if item["id"] == "slo_personalizado")
    assert p95["current"] is None
    assert custom["current"] is None
    assert custom["status"] == "sin_datos"


def test_run_drills_rejects_invalid_config_and_timing_shapes(monkeypatch: pytest.MonkeyPatch):
    config = _config()
    config["schema_version"] = 2
    with pytest.raises(ValueError, match="Configuración de SLO inválida"):
        run_drills(config, root=ROOT)

    with pytest.raises(ValueError, match="Timings de simulacro inválidos"):
        run_drills(_config(), timings={"rtsp_disconnected": cast("Any", None)}, root=ROOT)

    with pytest.raises(ValueError, match="Simulacros desconocidos"):
        run_drills(_config(), timings={"simulacro_inexistente": {}}, root=ROOT)

    monkeypatch.setattr(
        "vision_core.core.operations.incident_drills.validate_slo_config",
        lambda *args, **kwargs: [],
    )
    config = _config()
    config["drills"][0]["detection_objective_seconds"] = None
    with pytest.raises(ValueError, match="Objetivos inválidos"):
        run_drills(config, root=ROOT)
