import argparse
import json
import time
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from vision_core.core.config import Settings
from vision_core.core.model_registry.activation import resolve_active_models
from vision_core.features.reid.infrastructure.adapters.embedder import TorchvisionEmbeddingExtractor
from vision_core.scripts.benchmark_nightly import evaluate_budgets, load_budgets
from vision_core.scripts.create_benchmark_video import _frame
from vision_core.scripts.edge_benchmark_config import config_digest, load_config, select_profiles
from vision_core.scripts.edge_benchmark_metrics import (
    environment_metadata,
    read_energy_uj,
    sha256_file,
    summarize_latencies,
)
from vision_core.scripts.edge_benchmark_quality import (
    detection_quality_by_frame,
    evaluate_quality,
    identity_recall_at_1,
)
from vision_core.scripts.edge_benchmark_report import write_outputs

MEGABYTE = 1048576
CROP_RADIUS = 24
Box = tuple[float, float, float, float]
IdentityGallery = tuple[np.ndarray, np.ndarray]


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


def _load_identity_gallery(validation: dict) -> IdentityGallery | None:
    configured = validation.get("identity_gallery")
    if not configured:
        return None
    source = Path(configured)
    if not source.is_file():
        raise FileNotFoundError(f"No existe la galería de identidades: {source}")
    with np.load(source, allow_pickle=False) as data:
        embeddings = np.asarray(data["embeddings"], dtype=np.float32)
        labels = np.asarray(data["labels"]).astype(str)
    if embeddings.ndim != 2 or labels.ndim != 1 or embeddings.shape[0] != labels.shape[0]:
        raise ValueError("La galería de identidades requiere embeddings 2D y una etiqueta por embedding")
    return embeddings, labels


def _reference_boxes(frames: list[tuple[np.ndarray, dict]]) -> list[list[Box]]:
    boxes: list[list[Box]] = []
    for _, entry in frames:
        x = int(entry["x"])
        if entry["marker"] == "normal" and x >= 10:
            boxes.append([(float(x - 10), 100.0, float(x + 10), 140.0)])
        else:
            boxes.append([])
    return boxes


def _crops(frames: list[tuple[np.ndarray, dict]]) -> list[tuple[int, np.ndarray, str]]:
    crops: list[tuple[int, np.ndarray, str]] = []
    for index, (frame, entry) in enumerate(frames):
        x = int(entry["x"])
        if entry["marker"] != "normal" or not CROP_RADIUS <= x < frame.shape[1] - CROP_RADIUS:
            continue
        crop = frame[96:144, x - CROP_RADIUS : x + CROP_RADIUS]
        crops.append((index, crop, f"marker-{x}"))
    if not crops:
        raise ValueError("El conjunto de validación no produce recortes de identidad")
    return crops


def _measure_pipeline(
    detector,
    embedder,
    frames: list[tuple[np.ndarray, dict]],
    crops: list[tuple[int, np.ndarray, str]],
) -> tuple[dict, dict, list[float], list[list[Box]], np.ndarray, list[str]]:
    crops_by_index = {index: (crop, label) for index, crop, label in crops}
    detection_samples: list[float] = []
    embedding_samples: list[float] = []
    frame_samples: list[float] = []
    predictions: list[list[Box]] = []
    vectors: list[np.ndarray] = []
    labels: list[str] = []
    for index, (frame, _) in enumerate(frames):
        started = time.perf_counter()
        detection_started = time.perf_counter()
        detections = detector.process(frame)
        detection_samples.append((time.perf_counter() - detection_started) * 1000)
        predictions.append([(item.bbox.x1, item.bbox.y1, item.bbox.x2, item.bbox.y2) for item in detections])
        selected = crops_by_index.get(index)
        if selected is not None:
            crop, label = selected
            embedding_started = time.perf_counter()
            vector = embedder(crop)
            embedding_samples.append((time.perf_counter() - embedding_started) * 1000)
            vectors.append(vector)
            labels.append(label)
        frame_samples.append((time.perf_counter() - started) * 1000)
    embeddings = np.asarray(vectors, dtype=np.float32) if vectors else np.empty((0, 0), dtype=np.float32)
    return (
        summarize_latencies(detection_samples),
        summarize_latencies(embedding_samples),
        frame_samples,
        predictions,
        embeddings,
        labels,
    )


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
    identity_gallery: IdentityGallery | None,
) -> dict:
    identity: dict[str, str] = {}
    reason = _unsupported_reason(profile, allow_cuda=args.allow_cuda)
    if reason:
        return _empty_result(profile, status="unsupported", reason=reason, identity=identity)

    tracemalloc.start()
    try:
        settings = _settings_for_profile(profile, registry=args.registry, model_dir=args.model_dir)
        detection_path = args.model_dir / profile["detection"]["selector"]
        if not detection_path.is_file():
            reason = f"Artefacto de detección ausente: {detection_path}. Los pesos no se versionan en el repositorio."
            return _empty_result(profile, status="not_measured", reason=reason, identity=identity)
        if not args.allow_download and not _torchvision_weights_cached(profile["embedding"]["selector"]):
            reason = (
                "Pesos de torchvision sin caché local; use --allow-download para descargarlos fuera del repositorio."
            )
            return _empty_result(profile, status="not_measured", reason=reason, identity=identity)

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
        (
            detection_latency,
            embedding_latency,
            frame_samples,
            predictions,
            embeddings,
            labels,
        ) = _measure_pipeline(detector, embedder, frames, crops)
        memory_peak_mb = round(tracemalloc.get_traced_memory()[1] / MEGABYTE, 3)
        energy_end = read_energy_uj()
    except Exception as error:
        reason = f"Perfil omitido: {error}"
        return _empty_result(profile, status="not_measured", reason=reason, identity=identity)
    finally:
        tracemalloc.stop()

    energy_j = round((energy_end - energy_start) / 1_000_000, 3) if energy_start is not None and energy_end else None
    frame_summary = summarize_latencies(frame_samples)
    total_ms = sum(frame_samples)
    fps = round(len(frames) / (total_ms / 1000), 3) if total_ms else None
    detection_summary = detection_quality_by_frame(predictions, _reference_boxes(frames))
    if identity_gallery is None:
        identity_recall = None
    else:
        reference_embeddings, reference_labels = identity_gallery
        identity_recall = identity_recall_at_1(
            embeddings,
            reference_embeddings,
            expected_labels=np.asarray(labels, dtype=str),
            reference_labels=reference_labels,
        )
    identity_summary = {
        "recall_at_1_vs_gallery": identity_recall,
        "source": "labeled-gallery" if identity_gallery else "not-available",
        "samples": int(embeddings.shape[0]) if embeddings.ndim == 2 else 0,
    }
    quality_metrics = {"detection": detection_summary, "identity": identity_summary}
    quality = evaluate_quality(quality_metrics, None, config["quality_gates"])
    metrics = {
        "detection": detection_latency,
        "embedding": embedding_latency,
        "frame": frame_summary,
        "fps_end_to_end": fps,
        "fps_scope": "detection+embedding por frame sobre el conjunto de validación; sin decode/analytics",
        "memory_peak_tracemalloc_mb": memory_peak_mb,
        "energy_j": energy_j,
        "energy_source": "linux-powercap" if energy_j is not None else "not-exposed",
        "frames": len(frames),
        "crops": int(embeddings.shape[0]) if embeddings.ndim == 2 else 0,
    }
    budget_metrics = {
        "fps": fps or 0.0,
        "frame_p95_ms": frame_summary["p95_ms"] or 0.0,
        "inference_p95_ms": frame_summary["p95_ms"] or 0.0,
        "memory_peak_mb": memory_peak_mb,
    }
    target = config["hardware_targets"][profile["target"]]
    violations = evaluate_budgets(budget_metrics, budgets, target["budget_scenario"]) if quality["passed"] else []
    budget = {
        "passed": (not violations) if quality["passed"] else None,
        "violations": violations,
        "scenario": target["budget_scenario"],
    }
    return {
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


def _recommendations(config: dict, results: list[dict]) -> dict[str, dict]:
    baseline_id = config["quality_gates"]["baseline_profile"]
    recommendations = {}
    for target in config["hardware_targets"]:
        candidates = [row for row in results if row["target"] == target and row["recommended"]]
        if candidates:
            chosen = max(candidates, key=lambda row: row["metrics"]["fps_end_to_end"] or 0)
            recommendations[target] = {
                "profile": chosen["id"],
                "reason": "Pasa calidad y presupuesto; mayor FPS medido en este target.",
            }
            continue
        measured = [row for row in results if row["target"] == target and row["status"] == "measured"]
        if not measured:
            recommendations[target] = {
                "profile": None,
                "reason": "Sin medición en este target; no se recomienda variante.",
            }
            continue
        baseline = next((row for row in measured if row["id"] == baseline_id), None)
        recommendations[target] = {
            "profile": baseline["id"] if baseline else None,
            "reason": "Sin variante que pase calidad y presupuesto; se mantiene el baseline medido como rollback."
            if baseline
            else "Sin variante válida ni baseline medido en este target.",
        }
    return recommendations


def run(config: dict, *, args: argparse.Namespace) -> dict:
    budgets = load_budgets(args.budgets)
    profiles = select_profiles(config, target=args.target, profile_id=args.profile)
    validation = dict(config["validation_set"])
    if args.frames is not None:
        validation["frames"] = args.frames
    identity_gallery = _load_identity_gallery(validation)
    results = [
        _run_profile(
            profile,
            config=config,
            args=args,
            budgets=budgets,
            validation=validation,
            identity_gallery=identity_gallery,
        )
        for profile in profiles
    ]
    recommendations = _recommendations(config, results)
    digest = config_digest(args.config)
    return {
        "schema_version": 1,
        "kind": "edge-benchmark-matrix",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": {"path": str(args.config), "sha256": digest},
        "environment": environment_metadata(
            args.device,
            digest,
            devices=sorted({profile["device"] for profile in profiles}),
        ),
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
