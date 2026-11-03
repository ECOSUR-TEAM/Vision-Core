"""Run: python -m infrastructure.video.check_stream --frames 100"""
import argparse
import json
import os
import shutil
import subprocess
import time

import numpy as np
from .frame_validation import validate_frame
from .rtsp_video_source import RtspVideoSource


def probe(url, transport):
    if not shutil.which('ffprobe'):
        return {'status': 'unavailable', 'reason': 'Instala ffmpeg/ffprobe'}
    try:
        result = subprocess.run([
            'ffprobe', '-v', 'error', '-rtsp_transport', transport,
            '-select_streams', 'v:0', '-show_entries',
            'stream=codec_name,width,height,pix_fmt,avg_frame_rate',
            '-of', 'json', url,
        ], capture_output=True, text=True, timeout=15, check=True)
        streams = json.loads(result.stdout).get('streams', [])
        return {'status': 'ok' if streams else 'no_video', 'streams': streams}
    except (subprocess.SubprocessError, ValueError):
        return {'status': 'failed', 'reason': 'No se pudo inspeccionar el stream; revisa acceso y transporte'}


def measure(source, count, detector=None):
    reads, intervals, processing = [], [], []
    size = None
    previous = None
    start = time.perf_counter()
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
    def stats(values):
        return {key: float(value) * 1000 for key, value in zip(
            ('mean_ms', 'p95_ms', 'max_ms'),
            (np.mean(values), np.percentile(values, 95), max(values)))} if values else None
    return {'frames': count, 'width': size[0], 'height': size[1],
            'dtype': 'uint8', 'channels': 'BGR (contrato del decodificador)',
            'open_ms': (opened - start) * 1000,
            'consumption_fps': count / elapsed, 'read': stats(reads),
            'arrival_interval': stats(intervals), 'detector': stats(processing),
            'reconnections': getattr(source, 'reconnections', None),
            'detector_status': 'executed' if detector is not None else 'not_tested',
            'end_to_end_latency_ms': None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frames', type=int, default=100)
    parser.add_argument('--transport', choices=('tcp', 'udp'), default='tcp')
    parser.add_argument('--detector', action='store_true', help='Ejecutar detector real; falla si sigue pendiente')
    args = parser.parse_args()
    if args.frames < 1:
        parser.error('--frames debe ser positivo')
    os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'rtsp_transport;' + args.transport
    report = {'transport_requested': args.transport}
    try:
        source = RtspVideoSource.from_env()
        report['probe'] = probe(os.environ['VISION_CORE_RTSP_URL'], args.transport)
        detector = None
        if args.detector:
            from infrastructure.detection.yolo_detector_manager import YoloDetectorManager
            detector = YoloDetectorManager()
        report['measurement'] = measure(source, args.frames, detector)
        report['status'] = 'ok' if report['probe']['status'] == 'ok' else 'incomplete'
    except Exception as error:
        # Avoid outputting URLs/credentials from native exception text.
        report.update(status='failed', error_type=type(error).__name__)
    print(json.dumps(report, indent=2))
    return 0 if report['status'] == 'ok' else 1


if __name__ == '__main__':
    raise SystemExit(main())
