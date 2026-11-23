import argparse
import json
import time
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from vision_core.core.config import Settings
from vision_core.features.reid.infrastructure.adapters.embedder import TorchvisionEmbeddingExtractor
from vision_core.model_registry.activation import resolve_active_models
from vision_core.scripts.benchmark_nightly import evaluate_budgets, load_budgets
from vision_core.scripts.create_benchmark_video import _frame
from vision_core.scripts.edge_benchmark_config import config_digest, load_config, select_profiles
from vision_core.scripts.edge_benchmark_metrics import (
    environment_metadata,
    read_energy_uj,
    sha256_file,
    summarize_latencies,
)
from vision_core.scripts.edge_benchmark_quality import detection_quality, evaluate_quality, identity_recall_at_1
from vision_core.scripts.edge_benchmark_report import write_outputs

MEGABYTE = 1048576
JITTER_FRAMES = 3
CROP_RADIUS = 24


def _settings_for_profile(profile: dict, *, registry: Path, model_dir: Path) -> Settings:
    detection = profile["detection"]
    embedding = profile["embedding"]
    env = {
        "VISION_CORE_VIDEO_SOURCE": "rtsp",
        "VISION_CORE_RTSP_URL": "rtsp://localhost:8554/benchmark",
        "VISION_CORE_MODEL_REGISTRY_FILE": str(registry),
        "VISION_CORE_DETECTION_MODEL_ID": detection["model_id"],
        "VISION_CORE_MODEL_PATH": str(model_dir / detection["selector"]),
        "VISION_CORE_DETECTION_PRECISION": detection["precision"],
        "VISION_CORE_DETECTION_DEVICE": profile["device"],
        "VISION_CORE_EMBEDDING_MODEL_ID": embedding["model_id"],
        "VISION_CORE_EMBEDDING_MODEL": embedding["selector"],
        "VISION_CORE_EMBEDDING_PRECISION": embedding["precision"],
        "VISION_CORE_EMBEDDING_DEVICE": profile["device"],
    }
    return Settings.from_env(env, validate_startup=False)


def _base_model(selector: str) -> str:
    for suffix in ("-int8", "-fp16"):
        if selector.endswith(suffix):
            return selector[: -len(suffix)]
    return selector


def _torchvision_weights_cached(selector: str) -> bool:
    try:
        import torch
    except ImportError:
        return False
    checkpoints = Path(torch.hub.get_dir()) / "checkpoints"
    prefix = f"{_base_model(selector)}-"
    return any(path.name.startswith(prefix) and path.suffix in {".pt", ".pth"} for path in checkpoints.glob("*"))


def _unsupported_reason(profile: dict, *, allow_cuda: bool) -> str | None:
    device = profile["device"]
    if device == "cuda" and not allow_cuda:
        return "Perfil CUDA omitido: la suite no requiere CUDA; use --allow-cuda en hardware compatible."
    if device == "cpu" and any(profile[role]["precision"] == "fp16" for role in ("detection", "embedding")):
        return "FP16 no está soportado en CPU; se mide solo en perfiles CUDA."
    return None


def _load_validation_frames(validation: dict, frames_requested: int) -> list[tuple[np.ndarray, dict]]:
    scene_path = Path(validation["scene"])
    if not scene_path.is_file():
        raise FileNotFoundError(f"No existe el scene de validación: {scene_path}")
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    entries = scene.get("entries", [])[:frames_requested]
    if not entries:
        raise ValueError("El scene de validación no tiene entradas")
    video_path = Path(validation["video"])
    captured: list[np.ndarray] = []
    if video_path.is_file():
        capture = cv2.VideoCapture(str(video_path))
        try:
            while len(captured) < len(entries):
                ok, frame = capture.read()
                if not ok:
                    break
                captured.append(frame)
        finally:
            capture.release()
    frames = []
    for index, entry in enumerate(entries):
        if index < len(captured):
            frame = captured[index]
        else:
            frame = _frame(int(scene["width"]), int(scene["height"]), entry["marker"], int(entry["x"]))
        frames.append((frame, entry))
    return frames


def _reference_boxes(frames: list[tuple[np.ndarray, dict]]) -> list[tuple[float, float, float, float]]:
    boxes = []
    for _, entry in frames:
        x = int(entry["x"])
        if entry["marker"] != "normal" or x < 10:
            continue
        boxes.append((float(x - 10), 100.0, float(x + 10), 140.0))
    return boxes


def _crops(frames: list[tuple[np.ndarray, dict]]) -> list[np.ndarray]:
    crops = []
    for frame, entry in frames[: max(JITTER_FRAMES, 0)]:
        del entry
        crops.append(frame)
    selected = []
    for frame, entry in frames:
        x = int(entry["x"])
        if x < CROP_RADIUS or x >= frame.shape[1] - CROP_RADIUS:
            continue
        selected.append(frame[96:144, x - CROP_RADIUS : x + CROP_RADIUS])
    return selected or crops


def _measure_detection(
    detector, frames: list[tuple[np.ndarray, dict]]
) -> tuple[dict, list[list[tuple[float, float, float, float]]]]:
    samples: list[float] = []
    predictions: list[list[tuple[float, float, float, float]]] = []
    for frame, _ in frames:
        started = time.perf_counter()
        detections = detector.process(frame)
        samples.append((time.perf_counter() - started) * 1000)
        predictions.append([(item.bbox.x1, item.bbox.y1, item.bbox.x2, item.bbox.y2) for item in detections])
    return summarize_latencies(samples), predictions


def _measure_embedding(embedder, crops: list[np.ndarray]) -> tuple[dict, np.ndarray]:
    samples: list[float] = []
    vectors = []
    for crop in crops:
        started = time.perf_counter()
        vector = embedder(crop)
        samples.append((time.perf_counter() - started) * 1000)
        vectors.append(vector)
    return summarize_latencies(samples), np.asarray(vectors, dtype=np.float32)


def _empty_result(profile: dict, *, status: str, reason: str, identity: dict) -> dict:
    return {
        "id": profile["id"],
        "target": profile["target"],
        "device": profile["device"],
        "status": status,
        "reason": reason,
        "detection": profile["detection"],
        "embedding": profile["embedding"],
        "model_identity": identity,
        "metrics": {},
        "quality_metrics": {},
        "quality": {"passed": False, "evaluated_before_performance": True, "checks": {}},
        "budget": {"passed": None, "violations": []},
        "recommended": False,
    }


def _run_profile(
    profile: dict,
    *,
    config: dict,
    args: argparse.Namespace,
    budgets: dict,
    validation: dict,
    baseline_quality: dict | None,
    baseline_embeddings: np.ndarray | None,
) -> tuple[dict, np.ndarray | None]:
    identity: dict[str, str] = {}
    reason = _unsupported_reason(profile, allow_cuda=args.allow_cuda)
    if reason:
        return _empty_result(profile, status="unsupported", reason=reason, identity=identity), None

    settings = _settings_for_profile(profile, registry=args.registry, model_dir=args.model_dir)
    detection_path = args.model_dir / profile["detection"]["selector"]
    if not detection_path.is_file():
        reason = f"Artefacto de detección ausente: {detection_path}. Los pesos no se versionan en el repositorio."
        return _empty_result(profile, status="not_measured", reason=reason, identity=identity), None
    if not args.allow_download and not _torchvision_weights_cached(profile["embedding"]["selector"]):
        reason = "Pesos de torchvision sin caché local; use --allow-download para descargarlos fuera del repositorio."
        return _empty_result(profile, status="not_measured", reason=reason, identity=identity), None

    active = resolve_active_models(settings)
    identity = active.as_log_identity()
    from vision_core.features.detection.infrastructure.adapters.yolo_detector_manager import YoloDetectorManager

    detector = YoloDetectorManager(
        str(detection_path),
        device=profile["device"],
        precision=profile["detection"]["precision"],
        confidence=settings.detection.confidence,
        classes=settings.detection.classes,
        tracking_enabled=False,
        model_descriptor=active.detection,
    )
    embedder = TorchvisionEmbeddingExtractor(
        profile["embedding"]["selector"],
        profile["device"],
        active.embedding,
        profile["embedding"]["precision"],
    )
    frames = _load_validation_frames(validation, args.frames)
    crops = _crops(frames)

    energy_start = read_energy_uj()
    tracemalloc.start()
    try:
        detection_latency, predictions = _measure_detection(detector, frames)
        embedding_latency, embeddings = _measure_embedding(embedder, crops)
        memory_peak_mb = round(tracemalloc.get_traced_memory()[1] / MEGABYTE, 3)
    finally:
        tracemalloc.stop()
    energy_end = read_energy_uj()
    energy_j = round((energy_end - energy_start) / 1_000_000, 3) if energy_start is not None and energy_end else None

    elapsed = (detection_latency["samples"] * detection_latency["mean_ms"] or 0) + (
        embedding_latency["samples"] * embedding_latency["mean_ms"] or 0
    )
    fps = round(len(frames) / (elapsed / 1000), 3) if elapsed else None
    all_predictions = [box for frame_predictions in predictions for box in frame_predictions]
    detection_summary = detection_quality(all_predictions, _reference_boxes(frames))
    identity_summary = {
        "recall_at_1_vs_fp32": identity_recall_at_1(embeddings, baseline_embeddings)
        if baseline_embeddings is not None
        else (identity_recall_at_1(embeddings, embeddings) if embeddings.size else None),
        "samples": int(embeddings.shape[0]),
    }
    quality_metrics = {"detection": detection_summary, "identity": identity_summary}
    quality = evaluate_quality(quality_metrics, baseline_quality, config["quality_gates"])

    metrics = {
        "detection": detection_latency,
        "embedding": embedding_latency,
        "fps_end_to_end": fps,
        "fps_scope": "detection+embedding sobre el conjunto de validación; sin decode/analytics",
        "memory_peak_tracemalloc_mb": memory_peak_mb,
        "energy_j": energy_j,
        "energy_source": "linux-powercap" if energy_j is not None else "not-exposed",
        "frames": len(frames),
        "crops": int(embeddings.shape[0]),
    }
    budget_metrics = {
        "fps": fps or 0.0,
        "frame_p95_ms": (detection_latency["p95_ms"] or 0.0) + (embedding_latency["p95_ms"] or 0.0),
        "inference_p95_ms": detection_latency["p95_ms"] or 0.0,
        "memory_peak_mb": memory_peak_mb,
    }
    target = config["hardware_targets"][profile["target"]]
    violations = evaluate_budgets(budget_metrics, budgets, target["budget_scenario"]) if quality["passed"] else []
    budget = {
        "passed": (not violations) if quality["passed"] else None,
        "violations": violations,
        "scenario": target["budget_scenario"],
    }
    result = {
        "id": profile["id"],
        "target": profile["target"],
        "device": profile["device"],
        "status": "measured",
        "reason": None,
        "detection": profile["detection"],
        "embedding": profile["embedding"],
        "model_identity": identity,
        "artifact_sha256": sha256_file(detection_path),
        "metrics": metrics,
        "quality_metrics": quality_metrics,
        "quality": quality,
        "budget": budget,
        "recommended": bool(quality["passed"] and budget["passed"]),
    }
    return result, embeddings


def _recommendations(config: dict, results: list[dict]) -> dict[str, dict]:
    baseline_id = config["quality_gates"]["baseline_profile"]
    baseline = next((row for row in results if row["id"] == baseline_id), None)
    recommendations = {}
    for target in config["hardware_targets"]:
        candidates = [row for row in results if row["target"] == target and row["recommended"]]
        fallback = baseline or next((row for row in results if row["target"] == target), None)
        chosen = max(candidates, key=lambda row: row["metrics"]["fps_end_to_end"] or 0) if candidates else fallback
        if chosen is None:
            recommendations[target] = {"profile": None, "reason": "Sin perfiles para el target."}
        elif candidates:
            recommendations[target] = {
                "profile": chosen["id"],
                "reason": "Pasa calidad y presupuesto; mayor FPS medido en este target.",
            }
        else:
            recommendations[target] = {
                "profile": chosen["id"],
                "reason": "Sin evidencia suficiente: se mantiene FP32 como rollback hasta medir.",
            }
    return recommendations


def run(config: dict, *, args: argparse.Namespace) -> dict:
    budgets = load_budgets(args.budgets)
    profiles = select_profiles(config, target=args.target, profile_id=args.profile)
    baseline_id = config["quality_gates"]["baseline_profile"]
    ordered = sorted(profiles, key=lambda profile: profile["id"] != baseline_id)
    validation = dict(config["validation_set"])
    if args.frames is not None:
        validation["frames"] = args.frames

    results: list[dict] = []
    baseline_quality: dict | None = None
    baseline_embeddings: np.ndarray | None = None
    for profile in ordered:
        row, embeddings = _run_profile(
            profile,
            config=config,
            args=args,
            budgets=budgets,
            validation=validation,
            baseline_quality=baseline_quality,
            baseline_embeddings=baseline_embeddings,
        )
        if profile["id"] == baseline_id and row["status"] == "measured":
            baseline_quality = row["quality_metrics"]
            baseline_embeddings = embeddings
        results.append(row)

    recommendations = _recommendations(config, results)
    digest = config_digest(args.config)
    return {
        "schema_version": 1,
        "kind": "edge-benchmark-matrix",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": {"path": str(args.config), "sha256": digest},
        "environment": environment_metadata(args.device, digest),
        "hardware_targets": config["hardware_targets"],
        "validation_set": validation,
        "quality_gates": config["quality_gates"],
        "results": results,
        "recommendations": recommendations,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("benchmarks/edge-config.json"))
    parser.add_argument("--registry", type=Path, default=Path("config/models.yml"))
    parser.add_argument("--budgets", type=Path, default=Path("benchmarks/budgets.json"))
    parser.add_argument("--model-dir", type=Path, default=Path("models"))
    parser.add_argument("--output", type=Path, default=Path("benchmarks/edge-matrix.json"))
    parser.add_argument("--target")
    parser.add_argument("--profile")
    parser.add_argument("--frames", type=int)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--allow-download", action="store_true")
    parser.add_argument("--allow-cuda", action="store_true")
    parser.add_argument("--require-models", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    config = load_config(args.config)
    for path in (args.registry, args.budgets):
        if not path.is_file():
            parser.error(f"No existe el archivo: {path}")
    if args.frames is not None and args.frames < 1:
        parser.error("--frames debe ser positivo")
    matrix = run(config, args=args)
    paths = write_outputs(matrix, args.output)
    print(json.dumps({"outputs": {key: str(value) for key, value in paths.items()}}, indent=2))
    missing = [row["id"] for row in matrix["results"] if row["status"] != "measured"]
    if args.require_models and missing:
        print(f"Perfiles sin medir: {', '.join(missing)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
