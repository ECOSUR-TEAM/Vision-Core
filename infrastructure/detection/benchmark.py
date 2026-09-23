"""Measure real video decoding and detection/tracking without dropping frames."""

import argparse
import json
import math
from pathlib import Path
from time import perf_counter

import cv2

from domain.ports import DetectorManager
from infrastructure.detection.yolo_detector_manager import YoloDetectorManager


def benchmark_video(
    video_path: str, detector: DetectorManager, seconds: float = 30.0
) -> dict:
    """Measure at least 30s of constant-frame-rate video, including cold inference.

    Model construction is excluded. process_fps includes the entire process()
    call; pipeline_fps also includes decoding. No display, skipping or resizing.
    Use a fresh detector for each run so tracking starts with the first frame.
    """
    if not math.isfinite(seconds) or seconds < 30:
        raise ValueError("El benchmark requiere al menos 30 segundos de video")
    capture = cv2.VideoCapture(video_path)
    try:
        if not capture.isOpened():
            raise ValueError(f"No se pudo abrir el video: {video_path}")
        source_fps = capture.get(cv2.CAP_PROP_FPS)
        if not math.isfinite(source_fps) or source_fps <= 0:
            raise ValueError("El video no informa un FPS válido")
        target_frames = math.ceil(seconds * source_fps)
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        process_seconds = 0.0
        detections_count = 0
        started = perf_counter()
        for index in range(target_frames):
            ok, frame = capture.read()
            if not ok:
                raise ValueError(
                    f"Video insuficiente o ilegible: {index}/{target_frames} frames"
                )
            process_started = perf_counter()
            detections = detector.process(frame)
            process_seconds += perf_counter() - process_started
            detections_count += len(detections)
        pipeline_seconds = perf_counter() - started
        return {
            "video": str(video_path),
            "width": width,
            "height": height,
            "source_fps": source_fps,
            "frames": target_frames,
            "video_seconds": target_frames / source_fps,
            "detections": detections_count,
            "process_seconds": process_seconds,
            "process_fps": target_frames / process_seconds,
            "pipeline_seconds": pipeline_seconds,
            "pipeline_fps": target_frames / pipeline_seconds,
        }
    finally:
        capture.release()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    for path in (args.video, args.model):
        if not path.is_file():
            parser.error(f"No existe el archivo local: {path}")
    if not math.isfinite(args.seconds) or args.seconds < 30:
        parser.error("--seconds debe ser finito y >= 30")
    detector = YoloDetectorManager(str(args.model))
    result = benchmark_video(str(args.video), detector, args.seconds)
    result["model"] = str(args.model)
    report = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(report + "\n", encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
