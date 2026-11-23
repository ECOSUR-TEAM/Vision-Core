"""Pruebas rápidas de la matriz comparativa edge / INT8."""

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from vision_core.scripts import benchmark_edge
from vision_core.scripts.edge_benchmark_config import load_config, select_profiles, validate_config
from vision_core.scripts.edge_benchmark_metrics import percentile, summarize_latencies
from vision_core.scripts.edge_benchmark_quality import (
    box_iou,
    detection_quality_by_frame,
    evaluate_quality,
    identity_recall_at_1,
)
from vision_core.scripts.edge_benchmark_report import flatten_row, write_outputs

ROOT = Path(__file__).resolve().parents[2]
EDGE_CONFIG = ROOT / "benchmarks" / "edge-config.json"


def test_edge_config_and_profile_selection():
    config = load_config(EDGE_CONFIG)
    assert {profile["id"] for profile in config["profiles"]} == {
        "cpu-fp32",
        "cpu-int8",
        "jetson-fp32",
        "jetson-int8",
        "gpu-fp16",
    }
    selected = select_profiles(config, target="jetson-nano-int8")
    assert {profile["id"] for profile in selected} == {"jetson-fp32", "jetson-int8"}
    assert select_profiles(config, profile_id="cpu-int8")[0]["embedding"]["precision"] == "int8"
    with pytest.raises(ValueError, match="Perfil desconocido"):
        select_profiles(config, profile_id="inexistente")


def test_edge_config_rejects_invalid_schema():
    config = load_config(EDGE_CONFIG)
    broken = copy.deepcopy(config)
    broken["schema_version"] = 2
    with pytest.raises(ValueError, match="schema_version"):
        validate_config(broken)


def test_unsupported_profiles_do_not_require_models():
    cuda = {"device": "cuda", "detection": {"precision": "fp16"}, "embedding": {"precision": "fp16"}}
    cpu_fp16 = {"device": "cpu", "detection": {"precision": "fp16"}, "embedding": {"precision": "fp32"}}
    cpu_fp32 = {"device": "cpu", "detection": {"precision": "fp32"}, "embedding": {"precision": "fp32"}}
    assert "CUDA" in benchmark_edge._unsupported_reason(cuda, allow_cuda=False)
    assert "FP16" in benchmark_edge._unsupported_reason(cpu_fp16, allow_cuda=False)
    assert benchmark_edge._unsupported_reason(cpu_fp32, allow_cuda=False) is None


def test_quality_gates_apply_relative_floor():
    quality = {"detection": {"map50_proxy": 0.95}, "identity": {"recall_at_1_vs_gallery": 0.98}}
    gates = {
        "min_detection_map50": 0.9,
        "min_identity_recall_at_1": 0.9,
        "max_relative_drop_pct": 5.0,
    }
    baseline = {"detection": {"map50_proxy": 0.96}, "identity": {"recall_at_1_vs_gallery": 0.99}}
    result = evaluate_quality(quality, baseline, gates)
    assert result["passed"] is True
    assert result["evaluated_before_performance"] is True
    quality["detection"]["map50_proxy"] = 0.9
    result = evaluate_quality(quality, baseline, gates)
    assert result["passed"] is False
    assert result["checks"]["detection_map50"]["passed"] is False


def test_identity_gate_fails_without_labeled_gallery():
    gates = {
        "min_detection_map50": 0.9,
        "min_identity_recall_at_1": 0.9,
        "max_relative_drop_pct": 5.0,
    }
    quality = {
        "detection": {"map50_proxy": 0.99},
        "identity": {"recall_at_1_vs_gallery": None, "source": "not-available"},
    }
    result = evaluate_quality(quality, None, gates)
    assert result["passed"] is False
    assert result["checks"]["identity_recall_at_1"]["reason"] == "sin_medicion"


def test_box_iou_detection_by_frame_and_identity_recall():
    assert box_iou((0, 0, 10, 10), (5, 5, 15, 15)) == pytest.approx(25 / 175)
    assert box_iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0
    quality = detection_quality_by_frame(
        [[(0.0, 0.0, 10.0, 10.0)], []],
        [[(1.0, 1.0, 11.0, 11.0)], [(20.0, 20.0, 30.0, 30.0)]],
    )
    assert quality["matches"] == 1
    assert quality["map50_proxy"] == 0.5
    vectors = np.eye(3, dtype=np.float32)
    assert identity_recall_at_1(vectors, vectors) == 1.0
    assert (
        identity_recall_at_1(
            np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32),
            np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32),
            expected_labels=np.array(["a", "b"]),
            reference_labels=np.array(["b", "a"]),
        )
        == 0.0
    )


def test_percentiles_and_latency_summary():
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.5) == 2.5
    assert percentile([], 0.5) is None
    with pytest.raises(ValueError, match="quantile"):
        percentile([1.0], 1.5)
    summary = summarize_latencies([1.0, 2.0, 3.0])
    assert summary["samples"] == 3
    assert summary["p50_ms"] == 2.0


def test_matrix_recommendation_prefers_measured_and_rejects_unmeasured_targets():
    config = {
        "quality_gates": {"baseline_profile": "cpu-fp32"},
        "hardware_targets": {"cpu-laptop": {}, "gpu-fp16": {}},
    }
    results = [
        {
            "id": "cpu-fp32",
            "target": "cpu-laptop",
            "status": "measured",
            "recommended": False,
            "metrics": {},
        },
        {
            "id": "cpu-int8",
            "target": "cpu-laptop",
            "status": "measured",
            "recommended": True,
            "metrics": {"fps_end_to_end": 42.0},
        },
        {
            "id": "gpu-fp16",
            "target": "gpu-fp16",
            "status": "unsupported",
            "recommended": False,
            "metrics": {},
        },
    ]
    recommendations = benchmark_edge._recommendations(config, results)
    assert recommendations["cpu-laptop"]["profile"] == "cpu-int8"
    assert recommendations["gpu-fp16"]["profile"] is None
    assert "Sin medición" in recommendations["gpu-fp16"]["reason"]


def test_matrix_recommendation_keeps_measured_baseline_as_rollback():
    config = {
        "quality_gates": {"baseline_profile": "cpu-fp32"},
        "hardware_targets": {"jetson-nano-int8": {}},
    }
    results = [
        {
            "id": "jetson-fp32",
            "target": "jetson-nano-int8",
            "status": "measured",
            "recommended": False,
            "metrics": {},
        },
        {
            "id": "cpu-fp32",
            "target": "jetson-nano-int8",
            "status": "measured",
            "recommended": False,
            "metrics": {},
        },
    ]
    recommendations = benchmark_edge._recommendations(config, results)
    assert recommendations["jetson-nano-int8"]["profile"] == "cpu-fp32"
    assert "rollback" in recommendations["jetson-nano-int8"]["reason"]


def test_matrix_writes_json_csv_and_markdown(tmp_path):
    matrix = {
        "generated_at": "2026-11-22T00:00:00+00:00",
        "config": {"path": "benchmarks/edge-config.json", "sha256": "abc123def456"},
        "validation_set": {"seed": 20261120},
        "quality_gates": {"baseline_profile": "cpu-fp32"},
        "results": [
            {
                "id": "cpu-fp32",
                "target": "cpu-laptop",
                "status": "not_measured",
                "reason": "sin pesos",
                "detection": {"model_id": "detection.person.yolov8n", "precision": "fp32"},
                "embedding": {"model_id": "embedding.person.mobilenet_v3_small", "precision": "fp32"},
                "metrics": {},
                "quality": {"passed": False, "checks": {}},
                "budget": {"passed": None},
                "recommended": False,
            }
        ],
        "recommendations": {"cpu-laptop": {"profile": "cpu-fp32", "reason": "rollback"}},
    }
    paths = write_outputs(matrix, tmp_path / "edge-matrix.json")
    assert all(path.is_file() for path in paths.values())
    assert json.loads(paths["json"].read_text(encoding="utf-8")) == matrix
    assert "detection_model_id" in paths["csv"].read_text(encoding="utf-8")
    markdown = paths["markdown"].read_text(encoding="utf-8")
    assert "cpu-fp32" in markdown
    assert "rollback" in markdown
    assert flatten_row(matrix["results"][0])["embedding_precision"] == "fp32"


def test_run_without_models_does_not_recommend_targets(tmp_path):
    import argparse

    args = argparse.Namespace(
        config=EDGE_CONFIG,
        registry=ROOT / "config" / "models.yml",
        budgets=ROOT / "benchmarks" / "budgets.json",
        model_dir=tmp_path / "models",
        target=None,
        profile=None,
        frames=2,
        device="cpu",
        allow_download=False,
        allow_cuda=False,
    )
    matrix = benchmark_edge.run(load_config(EDGE_CONFIG), args=args)
    assert matrix["config"]["sha256"] == benchmark_edge.config_digest(EDGE_CONFIG)
    assert {row["status"] for row in matrix["results"]} <= {"not_measured", "unsupported"}
    assert all(recommendation["profile"] is None for recommendation in matrix["recommendations"].values())
