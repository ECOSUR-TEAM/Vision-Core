"""Run: python -m vision_core.scripts.check_stream --frames 100"""

import argparse
import json
import shutil
import subprocess
import time

import numpy as np

from vision_core.infrastructure.video.frame_validation import validate_frame
from vision_core.infrastructure.video.rtsp_video_source import RtspVideoSource
from vision_core.settings import Settings, apply_ffmpeg_capture_options
from vision_core.shared.errors import codes


def probe(url, transport):
    if not shutil.which("ffprobe"):
        return {"status": "unavailable", "reason": "Instala ffmpeg/ffprobe"}
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-rtsp_transport",
                transport,
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_name,width,height,pix_fmt,avg_frame_rate",
                "-of",
                "json",
                url,
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        )
        streams = json.loads(result.stdout).get("streams", [])
        return {"status": "ok" if streams else "no_video", "streams": streams}
    except (subprocess.SubprocessError, ValueError):
        return {
            "status": "failed",
            "code": codes.VIDEO_SOURCE_UNAVAILABLE,
            "reason": "No se pudo inspeccionar el stream; revisa acceso y transporte",
        }


def measure(source, count, detector=None):
    reads: list[float] = []
    intervals: list[float] = []
    processing: list[float] = []
    size: tuple[int, int] | None = None
    previous = None
    start = time.perf_counter()
    opened = start
    try:
        source.open()
        opened = time.perf_counter()
        for _ in range(count):
            before = time.perf_counter()
            frame = source.read_frame()
            received = time.perf_counter()
            validate_frame(frame, size)
            size = (frame.shape[1], frame.shape[0])
            reads.append(received - before)
            if previous is not None:
                intervals.append(received - previous)
            previous = received
            if detector is not None:
                detector.process(frame)
                processing.append(time.perf_counter() - received)
        elapsed = time.perf_counter() - opened
    finally:
        source.close()

    if size is None:
        raise RuntimeError("No se recibieron frames durante la medición")

    def stats(values: list[float]) -> dict[str, float] | None:
        if not values:
            return None
        statistics = (
            float(np.mean(values)),
            float(np.percentile(values, 95)),
            float(max(values)),
        )
        return {key: value * 1000 for key, value in zip(("mean_ms", "p95_ms", "max_ms"), statistics)}

    return {
        "frames": count,
        "width": size[0],
        "height": size[1],
        "dtype": "uint8",
        "channels": "BGR (contrato del decodificador)",
        "open_ms": (opened - start) * 1000,
        "consumption_fps": count / elapsed,
        "read": stats(reads),
        "arrival_interval": stats(intervals),
        "detector": stats(processing),
        "reconnections": getattr(source, "reconnections", None),
        "detector_status": "executed" if detector is not None else "not_tested",
        "end_to_end_latency_ms": None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=100)
    parser.add_argument("--transport", choices=("tcp", "udp"), default="tcp")
    parser.add_argument("--detector", action="store_true", help="Ejecutar detector real; falla si sigue pendiente")
    args = parser.parse_args()
    if args.frames < 1:
        parser.error("--frames debe ser positivo")
    settings = Settings.from_env()
    apply_ffmpeg_capture_options("rtsp_transport;" + args.transport)
    report = {"transport_requested": args.transport}
    try:
        source = RtspVideoSource.from_env()
        report["probe"] = probe(settings.video.rtsp_url or "", args.transport)
        detector = None
        if args.detector:
            from vision_core.infrastructure.detection.yolo_detector_manager import (
                YoloDetectorManager,
            )

            detector = YoloDetectorManager()
        report["measurement"] = measure(source, args.frames, detector)
        report["status"] = "ok" if report["probe"]["status"] == "ok" else "incomplete"
    except Exception as error:  # noqa: BLE001 - limit CLI exposure to exception type
        # Avoid outputting URLs/credentials from native exception text.
        report.update(status="failed", error_type=type(error).__name__)
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
