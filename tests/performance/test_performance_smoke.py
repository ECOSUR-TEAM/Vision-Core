"""Prueba de humo de rendimiento con umbral amplio para cada PR."""

import json
import os
from pathlib import Path

import pytest

from tests.fakes.fake_detector import FakeDetector
from vision_core.features.video.infrastructure.adapters.file_video_source import FileVideoSource
from vision_core.scripts.benchmark_nightly import evaluate_budgets, load_budgets, run_benchmark

pytestmark = pytest.mark.smoke
ROOT = Path(__file__).resolve().parents[2]


def test_performance_smoke_with_wide_budgets(synthetic_sample, synthetic_zones, synthetic_scene, tmp_path):
    detections, lost_ids, _ = synthetic_scene
    detector = FakeDetector(
        detections_per_frame=list(detections),
        lost_ids_per_call=[list(ids) for ids in lost_ids],
    )
    metrics = run_benchmark(
        source=FileVideoSource(synthetic_sample / "sample.avi"),
        zones=synthetic_zones,
        detector=detector,
        video_path=synthetic_sample / "sample.avi",
        output_dir=tmp_path / "smoke",
        scenario="pr-smoke",
        device="cpu",
        context="pytest-smoke",
    )
    budgets = load_budgets(ROOT / "benchmarks" / "budgets.json")

    assert metrics["frames"] == 35
    assert metrics["events"] == 5
    assert metrics["memory"]["final"]["source"] in {"tracemalloc", "proc-status"}
    assert metrics["memory_peak_tracemalloc_mb"] >= 0
    assert evaluate_budgets(metrics, budgets, "pr-smoke") == []

    report_path = os.getenv("VISION_CORE_SMOKE_REPORT")
    if report_path:
        Path(report_path).write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
