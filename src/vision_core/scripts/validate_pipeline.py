"""python -m vision_core.scripts.validate_pipeline --video recording.avi --zones zones.json"""

import argparse
import json
import platform
import time
from pathlib import Path

import numpy as np
import torch

from vision_core.core.config import Settings
from vision_core.core.errors import VisionCoreError, codes
from vision_core.core.serialization.events import event_to_json_dict
from vision_core.features.detection.infrastructure.adapters.yolo_detector_manager import (
    YoloDetectorManager,
)
from vision_core.features.door.infrastructure.adapters.polygon_door_analytics import PolygonDoorAnalytics
from vision_core.features.door.infrastructure.config.zone_loader import load_zones
from vision_core.features.reid.infrastructure.adapters.embedder import TorchvisionEmbeddingExtractor
from vision_core.features.reid.infrastructure.adapters.memory_reid import InMemoryReID
from vision_core.features.video.infrastructure.adapters.file_video_source import FileVideoSource
from vision_core.features.video.infrastructure.adapters.rtsp_video_source import RtspVideoSource
from vision_core.model_registry.activation import resolve_active_models
from vision_core.scripts.pipeline_tools.limited_source import LimitedSource
from vision_core.scripts.pipeline_tools.measured_app import MeasuredApp
from vision_core.scripts.pipeline_tools.recorded_detector import RecordedDetector


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", help="Si se omite, usa VISION_CORE_RTSP_URL")
    parser.add_argument("--zones", required=True)
    parser.add_argument("--model", default="yolov8n.pt")
    parser.add_argument("--frames", type=int, default=300)
    parser.add_argument("--output", required=True, help="Nuevo archivo JSONL")
    args = parser.parse_args()
    if args.frames <= 0:
        parser.error("--frames debe ser positivo")
    zones = load_zones(args.zones)
    active_models = resolve_active_models(Settings.from_env(validate_startup=False))
    source = LimitedSource(FileVideoSource(args.video) if args.video else RtspVideoSource.from_env(), args.frames)
    with Path(args.output).open("x") as output:
        start = time.perf_counter()
        try:
            detector = RecordedDetector(
                YoloDetectorManager(args.model, model_descriptor=active_models.detection), output
            )

            def emit(event):
                output.write(json.dumps({"kind": "event", "frame": source.frames, **event_to_json_dict(event)}) + "\n")

            app = MeasuredApp(
                source,
                detector,
                InMemoryReID.from_env(),
                PolygonDoorAnalytics(zones.exterior, zones.interior, zones.door),
                TorchvisionEmbeddingExtractor.from_env(active_models.embedding),
                emit,
                expected_frame_size=(zones.width, zones.height),
                output=output,
            )
            run_start = time.perf_counter()
            app.run()
            run_seconds = time.perf_counter() - run_start
        except Exception as error:
            output.write(
                json.dumps(
                    {
                        "kind": "summary",
                        "status": "failed",
                        "code": error.code if isinstance(error, VisionCoreError) else codes.INTERNAL_ERROR,
                        "error_type": type(error).__name__,
                        "frames": source.frames,
                    }
                )
                + "\n"
            )
            raise
        output.write(
            json.dumps(
                {
                    "kind": "summary",
                    "status": "completed",
                    "frames": source.frames,
                    "seconds": time.perf_counter() - start,
                    "reconnections": getattr(source.source, "reconnections", 0),
                    "processing_fps": source.frames / sum(app.durations) if app.durations else None,
                    "pipeline_fps": source.frames / run_seconds,
                    "processing_ms": {
                        key: float(np.percentile(app.durations, percentile)) * 1000
                        for key, percentile in [("p50", 50), ("p95", 95), ("p99", 99)]
                    }
                    if app.durations
                    else None,
                    "mean_read_ms": float(np.mean(source.read_seconds)) * 1000 if source.read_seconds else None,
                    "capture_to_event_latency_ms": None,
                    "environment": {
                        "platform": platform.platform(),
                        "torch": torch.__version__,
                        "cuda_available": torch.cuda.is_available(),
                        "model": args.model,
                    },
                }
            )
            + "\n"
        )


if __name__ == "__main__":
    main()
