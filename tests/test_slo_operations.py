"""Tests para SLOs, alertas, tablero y simulacros de ECM-104."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vision_core.core.errors.codes import ALL_CODES
from vision_core.core.operations.incident_drills import render_incident_drills, run_incident_drills
from vision_core.core.operations.slo import (
    ROOT,
    build_slo_report,
    load_json,
    render_slo_dashboard,
    validate_slo_config,
)

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
            "gauges": {"vision_core_fps": 15.0},
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


def test_validate_rejects_alert_without_existing_runbook():
    config = _config()
    config["slos"][0]["alert"]["runbook"] = "docs/runbooks/no-existe.md"

    errors = validate_slo_config(config, root=ROOT)

    assert any("no existe" in error for error in errors)


def test_validate_rejects_unknown_error_codes():
    config = _config()
    config["slos"][0]["error_codes"].append("FROZEN_FRAME")

    errors = validate_slo_config(config, root=ROOT)

    assert any("desconocidos" in error for error in errors)


def test_validate_rejects_orphan_drill():
    config = _config()
    config["drills"][0]["slo_id"] = "slo_inexistente"

    errors = validate_slo_config(config, root=ROOT)

    assert any("no apunta a un SLO" in error for error in errors)


def test_run_drills_records_all_scenarios():
    report = run_incident_drills(_config(), root=ROOT)

    assert report["summary"] == {"total": 6, "passed": 6, "failed": 0}
    assert {drill["id"] for drill in report["drills"]} == {
        "rtsp_disconnected",
        "frozen_frame",
        "weights_missing",
        "event_sink_down",
        "disk_full",
        "container_restart",
    }
    assert set(report["exercised_codes"]) <= set(ALL_CODES)
    assert all("detection_seconds" in drill for drill in report["drills"])
    assert all("recovery_seconds" in drill for drill in report["drills"])
    assert "Simulacro" in render_incident_drills(report)


def test_run_drills_marks_slow_recovery_as_failed():
    report = run_incident_drills(
        _config(),
        timings={"rtsp_disconnected": {"recovery_seconds": 999.0}},
        root=ROOT,
    )
    drill = next(item for item in report["drills"] if item["id"] == "rtsp_disconnected")

    assert drill["status"] == "failed"
    assert report["summary"]["failed"] == 1


def test_build_slo_report_uses_p95_and_marks_breach():
    snapshots = _snapshots()
    snapshots["metrics"]["histograms"]["vision_core_frame_processing_duration_ms"]["p95"] = 90.0

    report = _build(snapshots)
    entry = next(item for item in report["slos"] if item["id"] == "processing_p95")

    assert entry["current"] == 90.0
    assert entry["status"] == "brecha"
    assert entry["trend"] == "sin_datos_previos"


def test_build_slo_report_computes_trend_from_history():
    snapshots = _snapshots()
    previous = {"processing_p95": 30.0}

    report = _build(snapshots, previous=previous)
    entry = next(item for item in report["slos"] if item["id"] == "processing_p95")

    assert entry["trend"] == "empeorando"


def test_render_dashboard_links_each_alert_runbook():
    report = _build(_snapshots())
    markdown = render_slo_dashboard(report)

    assert markdown.count("../docs/runbooks/") == 5
    assert "critical" in markdown
    assert "warning" in markdown


def test_check_slo_config_cli_accepts_repo_config(tmp_path: Path):
    output = tmp_path / "config.json"
    output.write_text(json.dumps(_config()), encoding="utf-8")

    assert validate_slo_config(load_json(output), root=ROOT) == []
